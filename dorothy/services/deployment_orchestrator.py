import requests
import time
import uuid
import threading
from typing import Dict, List, Optional
from pathlib import Path
from config import config

class DeploymentOrchestrator:
    """Orchestrates bot deployments by calling Sally to execute commands"""

    def __init__(self):
        self.sally_url = config.sally_url
        self.deployments = {}
        self.verifications = {}
        self.templates_dir = Path(__file__).parent.parent / 'templates'

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

    def _load_template(self, template_name: str, **kwargs) -> str:
        """Load and fill in template file"""
        template_path = self.templates_dir / template_name
        with open(template_path, 'r') as f:
            template = f.read()
        return template.format(**kwargs)

    def verify_nginx_config(self, server: str, bot_name: str) -> Dict:
        """Verify nginx configuration exists and is valid"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'nginx_config', 'success': False, 'error': f"Bot {bot_name} not configured"}

        nginx_config_name = bot_config.get('nginx_config_name', bot_name)

        # Check if nginx config exists
        check_result = self._call_sally(
            server,
            f"test -f /etc/nginx/sites-available/{nginx_config_name} && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            check_result['check'] = 'nginx_config'
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # Test nginx config syntax
        syntax_result = self._call_sally(server, "sudo nginx -t 2>&1")

        return {
            'check': 'nginx_config',
            'success': exists and syntax_result.get('exit_code') == 0,
            'exists': exists,
            'syntax_valid': syntax_result.get('exit_code') == 0,
            'details': f"Config exists: {exists}, Syntax valid: {syntax_result.get('exit_code') == 0}",
            'path': f"/etc/nginx/sites-available/{nginx_config_name}",
            'command': check_result.get('command')
        }

    def verify_gunicorn_service(self, server: str, bot_name: str) -> Dict:
        """Verify gunicorn service file exists and status"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'gunicorn_service', 'success': False, 'error': f"Bot {bot_name} not configured"}

        service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")

        # Check if service file exists
        check_result = self._call_sally(
            server,
            f"test -f /etc/systemd/system/{service_name}.service && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            check_result['check'] = 'gunicorn_service'
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # Check service status
        status_result = self._call_sally(
            server,
            f"sudo systemctl is-active {service_name}"
        )

        is_running = 'active' in status_result.get('stdout', '')

        return {
            'check': 'gunicorn_service',
            'success': exists,
            'exists': exists,
            'running': is_running,
            'service_name': service_name,
            'details': f"Service exists: {exists}, Running: {is_running}",
            'path': f"/etc/systemd/system/{service_name}.service",
            'command': check_result.get('command')
        }

    def verify_ssl_certificate(self, server: str, bot_name: str) -> Dict:
        """Verify SSL certificate exists and is valid"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'ssl_certificate', 'success': False, 'error': f"Bot {bot_name} not configured"}

        domain = bot_config.get('domain', f"{bot_name}.example.com")

        # Check if certificate exists
        check_result = self._call_sally(
            server,
            f"sudo test -f /etc/letsencrypt/live/{domain}/fullchain.pem && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            check_result['check'] = 'ssl_certificate'
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

        # Build result with helpful details
        result = {
            'check': 'ssl_certificate',
            'success': exists,
            'exists': exists,
            'domain': domain,
            'path': f"/etc/letsencrypt/live/{domain}/fullchain.pem",
            'command': check_result.get('command')
        }

        if exists:
            result['expiry'] = expiry
            result['details'] = f"Certificate exists for {domain}" + (f", expires: {expiry}" if expiry else "")
        else:
            result['details'] = f"Certificate not found for {domain}. Use certbot to set up SSL."
            # Include command output to help diagnose permission issues
            if check_result.get('stderr'):
                result['error'] = check_result.get('stderr')

        return result

    def verify_repository(self, server: str, bot_name: str) -> Dict:
        """Verify repository is cloned and up to date"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'repository', 'success': False, 'error': f"Bot {bot_name} not configured"}

        repo_path = bot_config.get('repo_path', '/var/www/bot-team')
        path = bot_config.get('path', f"/var/www/bot-team/{bot_name}")

        # Check if git repository exists (could be at repo_path for monorepo or path for separate repos)
        check_result = self._call_sally(
            server,
            f"test -d {repo_path}/.git && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            check_result['check'] = 'repository'
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # If exists, get current branch and status
        branch = None
        status = None
        if exists:
            branch_result = self._call_sally(server, f"cd {repo_path} && git branch --show-current")
            if branch_result.get('success'):
                branch = branch_result.get('stdout', '').strip()

            status_result = self._call_sally(server, f"cd {repo_path} && git status --short")
            if status_result.get('success'):
                status = status_result.get('stdout', '').strip()

        return {
            'check': 'repository',
            'success': exists,
            'exists': exists,
            'path': repo_path,
            'bot_path': path,
            'branch': branch,
            'status': status or 'clean',
            'details': f"Repository at {repo_path}, bot code at {path}",
            'command': check_result.get('command')
        }

    def verify_virtualenv(self, server: str, bot_name: str) -> Dict:
        """Verify virtual environment exists and has requirements installed"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'virtualenv', 'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path', f"/var/www/bot-team/{bot_name}")
        venv_path = f"{path}/.venv"

        # Check if venv exists
        check_result = self._call_sally(
            server,
            f"test -d {venv_path} && echo 'exists' || echo 'missing'"
        )

        if not check_result.get('success'):
            check_result['check'] = 'virtualenv'
            return check_result

        exists = 'exists' in check_result.get('stdout', '')

        # If exists, check if packages are installed
        packages_ok = False
        if exists:
            packages_result = self._call_sally(
                server,
                f"{venv_path}/bin/pip freeze | wc -l"
            )
            if packages_result.get('success'):
                count = packages_result.get('stdout', '').strip()
                packages_ok = int(count) > 0 if count.isdigit() else False

        return {
            'check': 'virtualenv',
            'success': exists,
            'exists': exists,
            'venv_path': venv_path,
            'packages_installed': packages_ok,
            'path': venv_path,
            'command': check_result.get('command')
        }

    def verify_permissions(self, server: str, bot_name: str) -> Dict:
        """Verify directory permissions are correct"""
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'check': 'permissions', 'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path', f"/var/www/bot-team/{bot_name}")

        # Check permissions and ownership
        check_result = self._call_sally(
            server,
            f"ls -ld {path}"
        )

        if not check_result.get('success'):
            check_result['check'] = 'permissions'
            return check_result

        return {
            'check': 'permissions',
            'success': check_result.get('success'),
            'details': check_result.get('stdout', '').strip(),
            'path': path,
            'command': check_result.get('command')
        }

    def _run_verification_checks(self, verification_id: str, server: str, bot_name: str):
        """Run verification checks in background, updating progress as we go"""
        verification = self.verifications[verification_id]
        checks = config.verification_checks

        # Get bot config to check if we should skip nginx-related checks
        bot_config = config.get_bot_config(bot_name)
        skip_nginx = bot_config.get('skip_nginx', False) if bot_config else False

        for check in checks:
            # Skip nginx and SSL checks for internal-only bots
            if skip_nginx and check in ['nginx_config', 'ssl_certificate']:
                check_status = {
                    'check': check,
                    'status': 'skipped',
                    'name': check.replace('_', ' ').title(),
                    'success': True,
                    'details': 'Skipped for internal-only bot (skip_nginx=true)'
                }
                verification['checks'].append(check_status)
                continue

            # Mark this check as in progress
            check_status = {
                'check': check,
                'status': 'in_progress',
                'name': check.replace('_', ' ').title()
            }
            verification['checks'].append(check_status)

            # Run the check
            check_method = getattr(self, f"verify_{check}", None)
            if check_method:
                result = check_method(server, bot_name)
                # Update the check with results
                check_status.update(result)
                check_status['status'] = 'completed' if result.get('success') else 'failed'
                if not result.get('success'):
                    verification['all_passed'] = False
            else:
                check_status.update({
                    'status': 'failed',
                    'success': False,
                    'error': f"Unknown check: {check}"
                })
                verification['all_passed'] = False

        verification['status'] = 'completed'
        verification['end_time'] = time.time()

    def verify_deployment(self, server: str, bot_name: str) -> Dict:
        """
        Start verification checks for a bot deployment (non-blocking)

        Args:
            server: Server name
            bot_name: Bot to verify

        Returns:
            Verification ID and initial status
        """
        verification_id = str(uuid.uuid4())[:8]

        verification = {
            'id': verification_id,
            'bot': bot_name,
            'server': server,
            'status': 'in_progress',
            'checks': [],
            'all_passed': True,
            'start_time': time.time()
        }

        self.verifications[verification_id] = verification

        # Run checks in background thread
        thread = threading.Thread(
            target=self._run_verification_checks,
            args=(verification_id, server, bot_name)
        )
        thread.daemon = True
        thread.start()

        return {
            'verification_id': verification_id,
            'status': 'started',
            'bot': bot_name,
            'server': server
        }

    def get_deployment_plan(self, server: str, bot_name: str) -> Dict:
        """
        Get the deployment plan without executing (dry-run)

        Shows all commands that would be executed during deployment

        Args:
            server: Server name
            bot_name: Bot to deploy

        Returns:
            Deployment plan with all commands
        """
        bot_config = config.get_bot_config(bot_name)

        if not bot_config:
            return {
                'success': False,
                'error': f"Bot {bot_name} not configured"
            }

        repo_path = bot_config.get('repo_path', '/var/www/bot-team')
        path = bot_config.get('path', f"/var/www/bot-team/{bot_name}")
        repo = bot_config.get('repo', '')
        domain = bot_config.get('domain', f"{bot_name}.example.com")
        service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")
        nginx_config_name = bot_config.get('nginx_config_name', bot_name)
        workers = bot_config.get('workers', 3)
        description = bot_config.get('description', bot_name)
        ssl_email = bot_config.get('ssl_email')
        skip_nginx = bot_config.get('skip_nginx', False)
        venv_path = f"{path}/.venv"

        # Build the plan
        plan = {
            'bot': bot_name,
            'server': server,
            'config': {
                'repo_path': repo_path,
                'path': path,
                'repo': repo,
                'domain': domain,
                'service': service_name,
                'workers': workers
            },
            'steps': []
        }

        # Step 1: Check and clone/update repository
        plan['steps'].append({
            'name': 'Repository setup',
            'description': 'Clone or update the git repository',
            'check_command': f"test -d {repo_path}/.git && echo 'exists' || echo 'missing'",
            'commands': {
                'if_exists': f"cd {repo_path} && sudo -u www-data git pull",
                'if_missing': f"sudo mkdir -p {repo_path} && cd {str(Path(repo_path).parent)} && sudo git clone {repo} {Path(repo_path).name} && sudo chown -R www-data:www-data {repo_path}"
            }
        })

        # Step 2: Virtual environment
        plan['steps'].append({
            'name': 'Virtual environment setup',
            'description': 'Create Python virtual environment if needed',
            'command': f"cd {path} && sudo -u www-data test -d .venv || sudo -u www-data python3 -m venv .venv"
        })

        # Step 3: Install dependencies
        plan['steps'].append({
            'name': 'Install dependencies',
            'description': 'Install Python packages from requirements.txt',
            'command': f"cd {path} && sudo -u www-data {venv_path}/bin/pip install -r requirements.txt"
        })

        # Step 4: Nginx config (skip for internal-only bots)
        if not skip_nginx:
            try:
                nginx_config = self._load_template(
                    'nginx.conf.template',
                    bot_name=bot_name,
                    bot_name_title=bot_name.title(),
                    description=description,
                    domain=domain,
                    bot_path=path
                )

                plan['steps'].append({
                    'name': 'Nginx configuration',
                    'description': 'Create nginx site configuration',
                    'config_content': nginx_config,
                    'commands': [
                        f"# Write config to /etc/nginx/sites-available/{nginx_config_name}",
                        f"sudo ln -sf /etc/nginx/sites-available/{nginx_config_name} /etc/nginx/sites-enabled/{nginx_config_name}",
                        f"sudo nginx -t"
                    ]
                })
            except Exception as e:
                plan['steps'].append({
                    'name': 'Nginx configuration',
                    'error': str(e)
                })

        # Step 5: Systemd service
        try:
            service_config = self._load_template(
                'gunicorn.service.template',
                bot_name=bot_name,
                bot_name_title=bot_name.title(),
                description=description,
                bot_path=path,
                workers=workers
            )

            plan['steps'].append({
                'name': 'Systemd service',
                'description': 'Create systemd service file',
                'config_content': service_config,
                'commands': [
                    f"# Write service to /etc/systemd/system/{service_name}.service",
                    f"sudo systemctl daemon-reload",
                    f"sudo systemctl enable {service_name}"
                ]
            })
        except Exception as e:
            plan['steps'].append({
                'name': 'Systemd service',
                'error': str(e)
            })

        # Step 6: SSL certificate (if configured and not skipping nginx)
        if ssl_email and not skip_nginx:
            plan['steps'].append({
                'name': 'SSL certificate',
                'description': f'Set up SSL certificate with certbot for {domain}',
                'command': f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email {ssl_email}"
            })

        # Step 7: Reload nginx (skip for internal-only bots)
        if not skip_nginx:
            plan['steps'].append({
                'name': 'Reload nginx',
                'description': 'Reload nginx to pick up new configuration',
                'command': 'sudo systemctl reload nginx'
            })

        # Step 8: Start service
        plan['steps'].append({
            'name': 'Start service',
            'description': 'Start or restart the gunicorn service',
            'command': f"sudo systemctl restart {service_name}"
        })

        return plan

    def _run_deployment(self, deployment_id: str, server: str, bot_name: str):
        """Run deployment in background, updating progress as we go"""
        deployment = self.deployments[deployment_id]
        bot_config = config.get_bot_config(bot_name)

        repo_path = bot_config.get('repo_path', '/var/www/bot-team')
        path = bot_config.get('path', f"/var/www/bot-team/{bot_name}")
        repo = bot_config.get('repo', '')
        domain = bot_config.get('domain', f"{bot_name}.example.com")
        service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")
        nginx_config_name = bot_config.get('nginx_config_name', bot_name)
        workers = bot_config.get('workers', 3)
        description = bot_config.get('description', bot_name)
        ssl_email = bot_config.get('ssl_email')
        skip_nginx = bot_config.get('skip_nginx', False)

        # Step 1: Clone/update repository
        deployment['steps'].append({'name': 'Repository setup', 'status': 'in_progress'})

        repo_check = self._call_sally(server, f"test -d {repo_path}/.git && echo 'exists' || echo 'missing'")

        if 'exists' in repo_check.get('stdout', ''):
            # Pull latest
            result = self._call_sally(server, f"cd {repo_path} && sudo -u www-data git pull")
        else:
            # Clone - create parent directory and clone
            parent_path = str(Path(repo_path).parent)
            repo_name = Path(repo_path).name
            result = self._call_sally(
                server,
                f"sudo mkdir -p {parent_path} && cd {parent_path} && sudo git clone {repo} {repo_name} && sudo chown -R www-data:www-data {repo_path}"
            )

        deployment['steps'][-1]['status'] = 'completed' if result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = {
            'success': result.get('success'),
            'stdout': result.get('stdout', ''),
            'stderr': result.get('stderr', ''),
            'exit_code': result.get('exit_code')
        }

        if not result.get('success'):
            deployment['status'] = 'failed'
            deployment['error'] = 'Repository setup failed'
            deployment['end_time'] = time.time()
            return deployment

        # Step 2: Set up virtual environment
        deployment['steps'].append({'name': 'Virtual environment setup', 'status': 'in_progress'})

        venv_path = f"{path}/.venv"
        venv_result = self._call_sally(
            server,
            f"cd {path} && sudo -u www-data test -d .venv || sudo -u www-data python3 -m venv .venv"
        )

        deployment['steps'][-1]['status'] = 'completed' if venv_result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = {
            'success': venv_result.get('success'),
            'stdout': venv_result.get('stdout', ''),
            'stderr': venv_result.get('stderr', ''),
            'exit_code': venv_result.get('exit_code')
        }

        # Step 3: Install dependencies
        deployment['steps'].append({'name': 'Install dependencies', 'status': 'in_progress'})

        install_result = self._call_sally(
            server,
            f"cd {path} && sudo -u www-data {venv_path}/bin/pip install -r requirements.txt",
            timeout=300
        )

        deployment['steps'][-1]['status'] = 'completed' if install_result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = {
            'success': install_result.get('success'),
            'stdout': install_result.get('stdout', ''),
            'stderr': install_result.get('stderr', ''),
            'exit_code': install_result.get('exit_code')
        }

        # Step 4: Create nginx config (skip for internal-only bots)
        if not skip_nginx:
            deployment['steps'].append({'name': 'Nginx configuration', 'status': 'in_progress'})

            try:
                nginx_config = self._load_template(
                    'nginx.conf.template',
                    bot_name=bot_name,
                    bot_name_title=bot_name.title(),
                    description=description,
                    domain=domain,
                    bot_path=path
                )

                # Escape quotes for shell
                nginx_config_escaped = nginx_config.replace("'", "'\\''")

                # Write nginx config
                nginx_result = self._call_sally(
                    server,
                    f"echo '{nginx_config_escaped}' | sudo tee /etc/nginx/sites-available/{nginx_config_name} > /dev/null && "
                    f"sudo ln -sf /etc/nginx/sites-available/{nginx_config_name} /etc/nginx/sites-enabled/{nginx_config_name} && "
                    f"sudo nginx -t"
                )

                deployment['steps'][-1]['status'] = 'completed' if nginx_result.get('success') else 'failed'
                deployment['steps'][-1]['result'] = {
                    'success': nginx_result.get('success'),
                    'stdout': nginx_result.get('stdout', ''),
                    'stderr': nginx_result.get('stderr', ''),
                    'exit_code': nginx_result.get('exit_code')
                }
            except Exception as e:
                deployment['steps'][-1]['status'] = 'failed'
                deployment['steps'][-1]['result'] = {
                    'success': False,
                    'error': str(e),
                    'stderr': str(e)
                }

        # Step 5: Create systemd service
        deployment['steps'].append({'name': 'Systemd service', 'status': 'in_progress'})

        try:
            service_config = self._load_template(
                'gunicorn.service.template',
                bot_name=bot_name,
                bot_name_title=bot_name.title(),
                description=description,
                bot_path=path,
                workers=workers
            )

            # Escape quotes for shell
            service_config_escaped = service_config.replace("'", "'\\''")

            # Write service file and reload systemd
            service_result = self._call_sally(
                server,
                f"echo '{service_config_escaped}' | sudo tee /etc/systemd/system/{service_name}.service > /dev/null && "
                f"sudo systemctl daemon-reload && "
                f"sudo systemctl enable {service_name}"
            )

            deployment['steps'][-1]['status'] = 'completed' if service_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': service_result.get('success'),
                'stdout': service_result.get('stdout', ''),
                'stderr': service_result.get('stderr', ''),
                'exit_code': service_result.get('exit_code')
            }
        except Exception as e:
            deployment['steps'][-1]['status'] = 'failed'
            deployment['steps'][-1]['result'] = {
                'success': False,
                'error': str(e),
                'stderr': str(e)
            }

        # Step 6: SSL certificate (if configured and not skipping nginx)
        if ssl_email and not skip_nginx:
            deployment['steps'].append({'name': 'SSL certificate', 'status': 'in_progress'})

            ssl_result = self._call_sally(
                server,
                f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email {ssl_email}",
                timeout=300
            )

            deployment['steps'][-1]['status'] = 'completed' if ssl_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': ssl_result.get('success'),
                'stdout': ssl_result.get('stdout', ''),
                'stderr': ssl_result.get('stderr', ''),
                'exit_code': ssl_result.get('exit_code')
            }

        # Step 7: Reload nginx (skip for internal-only bots)
        if not skip_nginx:
            deployment['steps'].append({'name': 'Reload nginx', 'status': 'in_progress'})

            reload_result = self._call_sally(server, "sudo systemctl reload nginx")
            deployment['steps'][-1]['status'] = 'completed' if reload_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': reload_result.get('success'),
                'stdout': reload_result.get('stdout', ''),
                'stderr': reload_result.get('stderr', ''),
                'exit_code': reload_result.get('exit_code')
            }

        # Step 8: Start/restart service
        deployment['steps'].append({'name': 'Start service', 'status': 'in_progress'})

        start_result = self._call_sally(server, f"sudo systemctl restart {service_name}")
        deployment['steps'][-1]['status'] = 'completed' if start_result.get('success') else 'failed'
        deployment['steps'][-1]['result'] = {
            'success': start_result.get('success'),
            'stdout': start_result.get('stdout', ''),
            'stderr': start_result.get('stderr', ''),
            'exit_code': start_result.get('exit_code')
        }

        # Final status
        all_succeeded = all(step['status'] == 'completed' for step in deployment['steps'])
        deployment['status'] = 'completed' if all_succeeded else 'partial'
        deployment['end_time'] = time.time()
        deployment['duration'] = deployment['end_time'] - deployment['start_time']

    def deploy_bot(self, server: str, bot_name: str) -> Dict:
        """
        Deploy a bot to a server (non-blocking)

        Full deployment workflow:
        - Clone/update repository
        - Set up virtual environment
        - Install dependencies
        - Create nginx config
        - Create systemd service
        - Set up SSL with certbot (if ssl_email is configured)
        - Reload nginx
        - Start the service

        Args:
            server: Server name
            bot_name: Bot to deploy

        Returns:
            Deployment ID and initial status
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

        # Run deployment in background thread
        thread = threading.Thread(
            target=self._run_deployment,
            args=(deployment_id, server, bot_name)
        )
        thread.daemon = True
        thread.start()

        return {
            'deployment_id': deployment_id,
            'status': 'started',
            'bot': bot_name,
            'server': server
        }

    def setup_ssl(self, server: str, bot_name: str, email: str) -> Dict:
        """
        Set up SSL certificate with certbot

        Args:
            server: Server name
            bot_name: Bot name
            email: Email for Let's Encrypt

        Returns:
            Result
        """
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        domain = bot_config.get('domain')

        result = self._call_sally(
            server,
            f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email {email}",
            timeout=300
        )

        return {
            'success': result.get('success'),
            'domain': domain,
            'output': result.get('stdout', ''),
            'error': result.get('stderr', '')
        }

    def get_deployment_status(self, deployment_id: str) -> Optional[Dict]:
        """Get status of a deployment"""
        return self.deployments.get(deployment_id)

    def get_verification_status(self, verification_id: str) -> Optional[Dict]:
        """Get status of a verification"""
        return self.verifications.get(verification_id)

# Global instance
deployment_orchestrator = DeploymentOrchestrator()
