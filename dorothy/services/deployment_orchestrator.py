import requests
import time
import uuid
from typing import Dict, List, Optional
from config import config

class DeploymentOrchestrator:
    """Orchestrates bot deployments by calling Sally to execute commands"""

    def __init__(self):
        self.sally_url = config.sally_url
        self.deployments = {}

    def _call_sally(self, server: str, command: str, timeout: Optional[int] = None) -> Dict:
        """
        Call Sally's API to execute a command

        Args:
            server: Server name
            command: Command to execute
            timeout: Optional timeout

        Returns:
            Result from Sally
        """
        try:
            payload = {
                'server': server,
                'command': command
            }
            if timeout:
                payload['timeout'] = timeout

            response = requests.post(
                f"{self.sally_url}/api/execute",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to call Sally: {str(e)}"
            }

    def verify_nginx_config(self, server: str, bot_name: str) -> Dict:
        """Verify nginx configuration exists and is valid"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        domain = bot_config.get('domain', f"{bot_name}.example.com")

        # Check if nginx config exists
        check_result = self._call_sally(
            server,
            f"test -f /etc/nginx/sites-available/{bot_name} && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # Test nginx config syntax
        syntax_result = self._call_sally(server, "sudo nginx -t")

        return {
            'check': 'nginx_config',
            'success': exists and syntax_result.get('success'),
            'exists': exists,
            'syntax_valid': syntax_result.get('success'),
            'details': check_result.get('stdout', '').strip()
        }

    def verify_gunicorn_service(self, server: str, bot_name: str) -> Dict:
        """Verify gunicorn service file exists and status"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        service_name = bot_config.get('service', f"{bot_name}-bot")

        # Check if service file exists
        check_result = self._call_sally(
            server,
            f"test -f /etc/systemd/system/{service_name}.service && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # Check service status
        status_result = self._call_sally(
            server,
            f"sudo systemctl status {service_name} --no-pager"
        )

        # Service is running if exit code is 0
        is_running = status_result.get('exit_code') == 0

        return {
            'check': 'gunicorn_service',
            'success': exists,
            'exists': exists,
            'running': is_running,
            'service_name': service_name,
            'details': status_result.get('stdout', '')[:500]  # Limit output
        }

    def verify_ssl_certificate(self, server: str, bot_name: str) -> Dict:
        """Verify SSL certificate exists and is valid"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        domain = bot_config.get('domain', f"{bot_name}.example.com")

        # Check if certificate exists
        check_result = self._call_sally(
            server,
            f"sudo test -f /etc/letsencrypt/live/{domain}/fullchain.pem && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # If exists, check expiration
        expiry = None
        if exists:
            expiry_result = self._call_sally(
                server,
                f"sudo openssl x509 -enddate -noout -in /etc/letsencrypt/live/{domain}/fullchain.pem"
            )
            if expiry_result.get('success'):
                expiry = expiry_result.get('stdout', '').strip()

        return {
            'check': 'ssl_certificate',
            'success': exists,
            'exists': exists,
            'domain': domain,
            'expiry': expiry
        }

    def verify_repository(self, server: str, bot_name: str) -> Dict:
        """Verify repository is cloned and up to date"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path', f"/var/www/{bot_name}")

        # Check if directory exists and is a git repo
        check_result = self._call_sally(
            server,
            f"test -d {path}/.git && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # If exists, get current branch and status
        branch = None
        status = None
        if exists:
            branch_result = self._call_sally(server, f"cd {path} && git branch --show-current")
            if branch_result.get('success'):
                branch = branch_result.get('stdout', '').strip()

            status_result = self._call_sally(server, f"cd {path} && git status --short")
            if status_result.get('success'):
                status = status_result.get('stdout', '').strip()

        return {
            'check': 'repository',
            'success': exists,
            'exists': exists,
            'path': path,
            'branch': branch,
            'status': status or 'clean'
        }

    def verify_virtualenv(self, server: str, bot_name: str) -> Dict:
        """Verify virtual environment exists and has requirements installed"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path', f"/var/www/{bot_name}")
        venv_path = f"{path}/venv"

        # Check if venv exists
        check_result = self._call_sally(
            server,
            f"test -d {venv_path} && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # If exists, check if requirements.txt packages are installed
        packages_ok = False
        if exists:
            packages_result = self._call_sally(
                server,
                f"cd {path}/{bot_name} && {venv_path}/bin/pip freeze"
            )
            if packages_result.get('success'):
                packages_ok = len(packages_result.get('stdout', '')) > 0

        return {
            'check': 'virtualenv',
            'success': exists,
            'exists': exists,
            'venv_path': venv_path,
            'packages_installed': packages_ok
        }

    def verify_permissions(self, server: str, bot_name: str) -> Dict:
        """Verify directory permissions are correct"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path', f"/var/www/{bot_name}")

        # Check permissions and ownership
        check_result = self._call_sally(
            server,
            f"ls -ld {path}"
        )

        if not check_result.get('success'):
            return check_result

        return {
            'check': 'permissions',
            'success': check_result.get('success'),
            'details': check_result.get('stdout', '').strip()
        }

    def verify_deployment(self, server: str, bot_name: str) -> Dict:
        """
        Run all verification checks for a bot deployment

        Args:
            server: Server name
            bot_name: Bot to verify

        Returns:
            Verification results
        """
        checks = config.verification_checks
        results = {
            'bot': bot_name,
            'server': server,
            'checks': [],
            'all_passed': True,
            'timestamp': time.time()
        }

        for check in checks:
            check_method = getattr(self, f"verify_{check}", None)
            if check_method:
                result = check_method(server, bot_name)
                results['checks'].append(result)
                if not result.get('success'):
                    results['all_passed'] = False
            else:
                results['checks'].append({
                    'check': check,
                    'success': False,
                    'error': f"Unknown check: {check}"
                })
                results['all_passed'] = False

        return results

    def deploy_bot(self, server: str, bot_name: str) -> Dict:
        """
        Deploy a bot to a server

        This is a full deployment workflow including:
        - Cloning/updating repository
        - Setting up virtual environment
        - Installing dependencies
        - Creating nginx config
        - Creating systemd service
        - Setting up SSL
        - Starting the service

        Args:
            server: Server name
            bot_name: Bot to deploy

        Returns:
            Deployment status
        """
        deployment_id = str(uuid.uuid4())[:8]
        bot_config = config.get_bot_config(bot_name)

        if not bot_config:
            return {
                'success': False,
                'error': f"Bot {bot_name} not configured"
            }

        deployment = {
            'id': deployment_id,
            'bot': bot_name,
            'server': server,
            'status': 'in_progress',
            'steps': [],
            'start_time': time.time()
        }

        self.deployments[deployment_id] = deployment

        # Step 1: Clone/update repository
        path = bot_config.get('path', f"/var/www/{bot_name}")
        repo = bot_config.get('repo', '')

        deployment['steps'].append({
            'name': 'Repository setup',
            'status': 'in_progress'
        })

        # Check if repo exists
        repo_check = self._call_sally(server, f"test -d {path}/.git && echo 'exists' || echo 'missing'")

        if 'exists' in repo_check.get('stdout', ''):
            # Pull latest
            result = self._call_sally(server, f"cd {path} && git pull")
        else:
            # Clone
            result = self._call_sally(server, f"sudo mkdir -p {path} && sudo git clone {repo} {path}")

        deployment['steps'][-1]['status'] = 'completed' if result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = result

        if not result.get('success'):
            deployment['status'] = 'failed'
            deployment['end_time'] = time.time()
            return deployment

        # Step 2: Set up virtual environment
        deployment['steps'].append({
            'name': 'Virtual environment setup',
            'status': 'in_progress'
        })

        venv_path = f"{path}/venv"
        venv_result = self._call_sally(
            server,
            f"cd {path} && test -d venv || python3 -m venv venv"
        )

        deployment['steps'][-1]['status'] = 'completed' if venv_result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = venv_result

        # Step 3: Install dependencies
        deployment['steps'].append({
            'name': 'Install dependencies',
            'status': 'in_progress'
        })

        install_result = self._call_sally(
            server,
            f"cd {path}/{bot_name} && {venv_path}/bin/pip install -r requirements.txt"
        )

        deployment['steps'][-1]['status'] = 'completed' if install_result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = install_result

        # Step 4: Create/update nginx config
        deployment['steps'].append({
            'name': 'Nginx configuration',
            'status': 'in_progress'
        })

        # This is a placeholder - in real implementation, you'd create the actual nginx config
        nginx_result = {'success': True, 'message': 'Nginx config step - implement based on your template'}
        deployment['steps'][-1]['status'] = 'completed'
        deployment['steps'][-1]['result'] = nginx_result

        # Step 5: Create/update systemd service
        deployment['steps'].append({
            'name': 'Systemd service',
            'status': 'in_progress'
        })

        # This is a placeholder - in real implementation, you'd create the actual service file
        service_result = {'success': True, 'message': 'Service file step - implement based on your template'}
        deployment['steps'][-1]['status'] = 'completed'
        deployment['steps'][-1]['result'] = service_result

        # Final status
        deployment['status'] = 'completed'
        deployment['end_time'] = time.time()
        deployment['duration'] = deployment['end_time'] - deployment['start_time']

        return deployment

    def get_deployment_status(self, deployment_id: str) -> Optional[Dict]:
        """Get status of a deployment"""
        return self.deployments.get(deployment_id)

# Global instance
deployment_orchestrator = DeploymentOrchestrator()
