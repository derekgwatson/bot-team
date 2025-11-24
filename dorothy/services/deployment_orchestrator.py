import requests
import time
import uuid
import threading
from typing import Dict,  Optional
from pathlib import Path
from dorothy.config import config
from shared.http_client import BotHttpClient
from shared.config.ports import get_port


class DeploymentOrchestrator:
    """Orchestrates bot deployments by calling Sally to execute commands"""

    def __init__(self):
        self.deployments = {}
        self.verifications = {}
        self.templates_dir = Path(__file__).parent.parent / 'templates'

        # Check if sudo is available/required (default: True for backward compatibility)
        # Set USE_SUDO=false in environment if sudo is not available
        import os
        use_sudo_env = os.getenv('USE_SUDO', 'true').lower()
        self.use_sudo = use_sudo_env in ('true', '1', 'yes')

    def _sudo(self, command: str) -> str:
        """
        Conditionally prefix a command with sudo if USE_SUDO is enabled.

        Args:
            command: The command to potentially prefix with sudo

        Returns:
            The command, optionally prefixed with 'sudo '
        """
        if self.use_sudo:
            return f"sudo {command}"
        return command

    def _get_bot_url(self, bot_name: str) -> str:
        """
        Get the URL for a bot.

        Logic:
        - If we're in a request context and session dev config says 'prod'
          for this bot, use the public HTTPS domain.
        - Otherwise, use localhost with the port from shared/config/ports.yaml.

        Returns the base URL for the bot API, e.g.:
            https://pam.watsonblinds.com.au    (prod)
            http://localhost:8004              (dev, from ports.yaml)
        """
        from flask import session, has_request_context

        # 1) Optional "prod" override from dev session
        if has_request_context():
            dev_config = session.get('dev_bot_config', {})
            if dev_config.get(bot_name) == 'prod':
                return f"https://{bot_name}.watsonblinds.com.au"

        # 2) Default: localhost + port from ports.yaml
        port = get_port(bot_name)
        if port is None:
            raise ValueError(
                f"No port configured for bot '{bot_name}' in shared/config/ports.yaml"
            )

        # Always use loopback for dev access
        return f"http://localhost:{port}"

    def check_sally_health(self) -> Dict:
        """
        Check if Sally is healthy and responding

        Returns:
            Dict with Sally's health status
        """
        sally_url = self._get_bot_url('sally')
        client = BotHttpClient(sally_url)

        try:
            response = client.get("health", timeout=5)
            response.raise_for_status()
            data = response.json()
            return {
                'success': True,
                'healthy': data.get('status') == 'healthy',
                'url': sally_url,
                'version': data.get('version'),
                'response_time_ms': int(response.elapsed.total_seconds() * 1000)
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'healthy': False,
                'url': sally_url,
                'error': 'Connection refused - Sally is not running or not accessible',
                'hint': f'Make sure Sally is running on {sally_url}'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'healthy': False,
                'url': sally_url,
                'error': 'Connection timeout - Sally is not responding',
                'hint': 'Sally may be running but overloaded or unresponsive'
            }
        except Exception as e:
            return {
                'success': False,
                'healthy': False,
                'url': sally_url,
                'error': f'Failed to check Sally health: {str(e)}'
            }

    def check_chester_health(self) -> Dict:
        """
        Check if Chester is healthy and responding

        Returns:
            Dict with Chester's health status
        """
        chester_url = self._get_bot_url('chester')
        client = BotHttpClient(chester_url)

        try:
            response = client.get("health", timeout=5)
            response.raise_for_status()
            data = response.json()
            return {
                'success': True,
                'healthy': data.get('status') == 'healthy',
                'url': chester_url,
                'version': data.get('version'),
                'response_time_ms': int(response.elapsed.total_seconds() * 1000)
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'healthy': False,
                'url': chester_url,
                'error': 'Connection refused - Chester is not running or not accessible',
                'hint': f'Make sure Chester is running on {chester_url}'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'healthy': False,
                'url': chester_url,
                'error': 'Connection timeout - Chester is not responding',
                'hint': 'Chester may be running but overloaded or unresponsive'
            }
        except Exception as e:
            return {
                'success': False,
                'healthy': False,
                'url': chester_url,
                'error': f'Failed to check Chester health: {str(e)}'
            }

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
        import os
        sally_url = self._get_bot_url('sally')
        client = BotHttpClient(sally_url)

        # Debug: Check if BOT_API_KEY is available
        api_key = os.getenv('BOT_API_KEY', '')
        if not api_key:
            print(f"⚠️  WARNING: BOT_API_KEY not set in environment!")
        else:
            print(f"✓ BOT_API_KEY is set (first 8 chars: {api_key[:8]}...)")

        try:
            payload = {
                'server': server,
                'command': command
            }
            if timeout:
                payload['timeout'] = timeout

            response = client.post("api/execute", json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            error_msg = f"Failed to call Sally: {str(e)}"

            # Add debug info if API key is missing
            if not api_key:
                error_msg += " [DEBUG: BOT_API_KEY not set in Dorothy's environment]"

            return {
                'success': False,
                'error': error_msg
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
        syntax_result = self._call_sally(server, f"{self._sudo('nginx -t 2>&1')}")

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
            self._sudo(f"systemctl is-active {service_name}")
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
            f"{self._sudo(f'test -f /etc/letsencrypt/live/{domain}/fullchain.pem')} && echo 'exists' || echo 'missing'"
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
                self._sudo(f"openssl x509 -enddate -noout -in /etc/letsencrypt/live/{domain}/fullchain.pem")
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
            branch_result = self._call_sally(server, f"cd {repo_path} && /usr/bin/git branch --show-current")
            if branch_result.get('success'):
                branch = branch_result.get('stdout', '').strip()

            status_result = self._call_sally(server, f"cd {repo_path} && /usr/bin/git status --short")
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
        """Verify root virtual environment exists (shared by all bots)"""
        # Check root venv (shared by all bots)
        venv_path = "/var/www/bot-team/.venv"

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
            'command': check_result.get('command'),
            'note': 'Using shared root venv for all bots'
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
        if self.use_sudo:
            git_pull_cmd = f"cd {repo_path} && sudo -u www-data /usr/bin/git pull"
            git_clone_cmd = f"sudo mkdir -p {Path(repo_path).parent} && cd {Path(repo_path).parent} && sudo /usr/bin/git clone {repo} {Path(repo_path).name} && sudo chown -R www-data:www-data {repo_path}"
        else:
            git_pull_cmd = f"cd {repo_path} && /usr/bin/git pull"
            git_clone_cmd = f"mkdir -p {Path(repo_path).parent} && cd {Path(repo_path).parent} && /usr/bin/git clone {repo} {Path(repo_path).name}"

        plan['steps'].append({
            'name': 'Repository setup',
            'description': 'Clone or update the git repository',
            'check_command': f"test -d {repo_path}/.git && echo 'exists' || echo 'missing'",
            'commands': {
                'if_exists': git_pull_cmd,
                'if_missing': git_clone_cmd
            }
        })

        # Step 2: Nginx config (skip for internal-only bots)
        # NOTE: Safe to overwrite - certbot step will re-add SSL config
        if not skip_nginx:
            try:
                port = get_port(bot_name)
                if not port:
                    raise ValueError(f"No port configured for {bot_name} in chester/config.yaml")

                nginx_config = self._load_template(
                    'nginx.conf.template',
                    bot_name=bot_name,
                    bot_name_title=bot_name.title(),
                    description=description,
                    domain=domain,
                    bot_path=path,
                    PORT=port
                )

                plan['steps'].append({
                    'name': 'Nginx configuration',
                    'description': 'Create/update nginx site configuration (SSL will be re-added by certbot)',
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

        # Step 3: Systemd service
        try:
            port = get_port(bot_name)
            if not port:
                raise ValueError(f"No port configured for {bot_name} in shared/config/ports.yaml")
            bind_config = f"0.0.0.0:{port}"

            service_config = self._load_template(
                'gunicorn.service.template',
                bot_name=bot_name,
                bot_name_title=bot_name.title(),
                description=description,
                bot_path=path,
                repo_path=repo_path,
                workers=workers,
                bind_config=bind_config
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

        # Step 4: SSL certificate (if configured and not skipping nginx)
        # Uses 'install' first (reinstalls existing cert config), falls back to full certbot (gets new cert)
        if ssl_email and not skip_nginx:
            plan['steps'].append({
                'name': 'SSL certificate',
                'description': f'Configure SSL for {domain} (reinstall existing or get new cert)',
                'command': (
                    f"sudo certbot install --nginx -d {domain} --non-interactive 2>/dev/null || "
                    f"sudo certbot --nginx -d {domain} --non-interactive --agree-tos --email {ssl_email}"
                )
            })

        # Step 5: Reload nginx (skip for internal-only bots)
        if not skip_nginx:
            plan['steps'].append({
                'name': 'Reload nginx',
                'description': 'Reload nginx to pick up new configuration',
                'command': 'sudo systemctl reload nginx'
            })

        # Step 6: Start service
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
            if self.use_sudo:
                result = self._call_sally(server, f"cd {repo_path} && sudo -u www-data /usr/bin/git pull")
            else:
                result = self._call_sally(server, f"cd {repo_path} && git pull")
        else:
            # Clone - create parent directory and clone
            parent_path = str(Path(repo_path).parent)
            repo_name = Path(repo_path).name
            if self.use_sudo:
                result = self._call_sally(
                    server,
                    f"sudo mkdir -p {parent_path} && cd {parent_path} && sudo /usr/bin/git clone {repo} {repo_name} && sudo chown -R www-data:www-data {repo_path}"
                )
            else:
                result = self._call_sally(
                    server,
                    f"mkdir -p {parent_path} && cd {parent_path} && git clone {repo} {repo_name}"
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
            error_parts = []
            if result.get('stderr'):
                error_parts.append(f"stderr: {result['stderr']}")
            if result.get('stdout'):
                error_parts.append(f"stdout: {result['stdout']}")
            if result.get('error'):
                error_parts.append(f"error: {result['error']}")
            if result.get('exit_code') is not None:
                error_parts.append(f"exit_code: {result['exit_code']}")

            error_details = ' | '.join(error_parts) if error_parts else 'No error details available'
            deployment['error'] = f"Repository setup failed: {error_details}"
            deployment['end_time'] = time.time()
            return deployment

        # Check if bot directory exists in the repository
        bot_dir_check = self._call_sally(server, f"test -d {path} && echo 'exists' || echo 'missing'")

        if 'missing' in bot_dir_check.get('stdout', ''):
            deployment['steps'][-1]['status'] = 'failed'
            deployment['steps'][-1]['result'] = {
                'success': False,
                'stdout': bot_dir_check.get('stdout', ''),
                'stderr': f"Bot directory not found: {path}\n\nThis usually means the bot's code hasn't been merged to the branch on the server yet.\nPlease merge your feature branch to main and try again.",
                'exit_code': 1
            }
            deployment['status'] = 'failed'
            deployment['error'] = f"Bot directory '{bot_name}' not found in repository"
            deployment['end_time'] = time.time()
            return deployment

        # Step 2: Create config files from examples if they don't exist
        deployment['steps'].append({'name': 'Configuration files setup', 'status': 'in_progress'})

        # Check and setup .env file
        if self.use_sudo:
            env_cmd = f"[ -f {path}/.env ] && echo 'exists' || ([ -f {path}/.env.example ] && sudo -u www-data cp {path}/.env.example {path}/.env && echo 'created' || echo 'no_example')"
        else:
            env_cmd = f"[ -f {path}/.env ] && echo 'exists' || ([ -f {path}/.env.example ] && cp {path}/.env.example {path}/.env && echo 'created' || echo 'no_example')"

        env_result = self._call_sally(server, env_cmd)

        # Check and setup config.local.yaml file
        if self.use_sudo:
            config_cmd = f"[ -f {path}/config.local.yaml ] && echo 'exists' || ([ -f {path}/config.local.yaml.example ] && sudo -u www-data cp {path}/config.local.yaml.example {path}/config.local.yaml && echo 'created' || echo 'no_example')"
        else:
            config_cmd = f"[ -f {path}/config.local.yaml ] && echo 'exists' || ([ -f {path}/config.local.yaml.example ] && cp {path}/config.local.yaml.example {path}/config.local.yaml && echo 'created' || echo 'no_example')"

        config_yaml_result = self._call_sally(server, config_cmd)

        # Build detailed result message
        env_status = env_result.get('stdout', '').strip()
        config_status = config_yaml_result.get('stdout', '').strip()

        result_messages = []
        warnings = []

        if 'exists' in env_status:
            result_messages.append("✅ .env file exists")
        elif 'created' in env_status:
            result_messages.append("✅ .env file created from .env.example")
        elif 'no_example' in env_status:
            warnings.append("⚠️ .env file missing and no .env.example found to copy")

        if 'exists' in config_status:
            result_messages.append("✅ config.local.yaml exists")
        elif 'created' in config_status:
            result_messages.append("✅ config.local.yaml created from config.local.yaml.example")
        elif 'no_example' in config_status:
            warnings.append("⚠️ config.local.yaml missing and no config.local.yaml.example found to copy")

        # This step is always marked as completed (it's informational/optional)
        deployment['steps'][-1]['status'] = 'completed'
        deployment['steps'][-1]['result'] = {
            'success': True,  # Always true since this is optional
            'stdout': '\n'.join(result_messages + warnings),
            'stderr': '',
            'details': 'Config file setup is optional - deployment continues regardless'
        }

        if warnings:
            deployment['steps'][-1]['result']['warning'] = 'Some config files missing (see details above)'

        # Step 4: DNS resolution check (for public domains only)
        if not skip_nginx:
            deployment['steps'].append({'name': 'DNS resolution check', 'status': 'in_progress'})

            # Get server's public IP address
            server_ip_result = self._call_sally(
                server,
                "curl -s ifconfig.me || curl -s icanhazip.com || curl -s api.ipify.org"
            )
            server_ip = server_ip_result.get('stdout', '').strip()

            # Check if domain resolves
            dns_result = self._call_sally(
                server,
                f"host {domain} || nslookup {domain} || dig {domain} +short"
            )

            deployment['steps'][-1]['status'] = 'completed' if dns_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': dns_result.get('success'),
                'stdout': dns_result.get('stdout', ''),
                'stderr': dns_result.get('stderr', ''),
                'exit_code': dns_result.get('exit_code'),
                'domain': domain,
                'server_ip': server_ip
            }

            # Fail fast if DNS doesn't resolve
            if not dns_result.get('success') or not dns_result.get('stdout', '').strip():
                deployment['status'] = 'failed'
                error_parts = []
                error_parts.append(f"Domain '{domain}' does not resolve to any IP address")
                error_parts.append("Please check:")
                error_parts.append("1. DNS records are configured correctly")
                error_parts.append("2. Domain name is spelled correctly in config")
                error_parts.append("3. DNS propagation has completed (can take up to 48 hours)")
                if dns_result.get('stderr'):
                    error_parts.append(f"DNS lookup error: {dns_result['stderr']}")
                deployment['error'] = '\n'.join(error_parts)
                deployment['end_time'] = time.time()
                return deployment

            # Verify domain resolves to this server's IP
            if server_ip:
                dns_output = dns_result.get('stdout', '')
                if server_ip not in dns_output:
                    deployment['status'] = 'failed'
                    deployment['steps'][-1]['status'] = 'failed'
                    error_parts = []
                    error_parts.append(f"DNS mismatch: '{domain}' does not resolve to this server")
                    error_parts.append(f"This server's IP: {server_ip}")
                    error_parts.append(f"Domain resolves to: {dns_output.strip()}")
                    error_parts.append("")
                    error_parts.append("This will cause certbot SSL certificate setup to fail.")
                    error_parts.append("Please update your DNS A record to point to the correct server IP.")
                    deployment['error'] = '\n'.join(error_parts)
                    deployment['end_time'] = time.time()
                    return deployment
            else:
                # Couldn't get server IP - log warning but continue
                deployment['steps'][-1]['result']['warning'] = 'Could not verify server IP match'

        # Step 5: Create nginx config (skip for internal-only bots)
        if not skip_nginx:
            deployment['steps'].append({'name': 'Nginx configuration', 'status': 'in_progress'})

            try:
                # Get port from shared configuration
                port = get_port(bot_name)
                if not port:
                    raise ValueError(f"No port configured for {bot_name} in shared/config/ports.yaml")

                nginx_config = self._load_template(
                    'nginx.conf.template',
                    bot_name=bot_name,
                    bot_name_title=bot_name.title(),
                    description=description,
                    domain=domain,
                    bot_path=path,
                    port=port
                )

                # Escape quotes for shell
                nginx_config_escaped = nginx_config.replace("'", "'\\''")

                # Write nginx config
                nginx_result = self._call_sally(
                    server,
                    f"echo '{nginx_config_escaped}' | {self._sudo('tee /etc/nginx/sites-available/' + nginx_config_name)} > /dev/null && "
                    f"{self._sudo('ln -sf /etc/nginx/sites-available/' + nginx_config_name + ' /etc/nginx/sites-enabled/' + nginx_config_name)} && "
                    f"{self._sudo('nginx -t')}"
                )

                deployment['steps'][-1]['status'] = 'completed' if nginx_result.get('success') else 'failed'
                deployment['steps'][-1]['result'] = {
                    'success': nginx_result.get('success'),
                    'stdout': nginx_result.get('stdout', ''),
                    'stderr': nginx_result.get('stderr', ''),
                    'exit_code': nginx_result.get('exit_code')
                }

                # Stop if nginx config failed
                if not nginx_result.get('success'):
                    deployment['status'] = 'failed'
                    error_parts = []
                    if nginx_result.get('stderr'):
                        error_parts.append(f"stderr: {nginx_result['stderr']}")
                    if nginx_result.get('stdout'):
                        error_parts.append(f"stdout: {nginx_result['stdout']}")
                    if nginx_result.get('error'):
                        error_parts.append(f"error: {nginx_result['error']}")
                    if nginx_result.get('exit_code') is not None:
                        error_parts.append(f"exit_code: {nginx_result['exit_code']}")
                    error_details = ' | '.join(error_parts) if error_parts else 'No error details available'
                    deployment['error'] = f"Nginx configuration failed: {error_details}"
                    deployment['end_time'] = time.time()
                    return deployment

            except Exception as e:
                deployment['steps'][-1]['status'] = 'failed'
                deployment['steps'][-1]['result'] = {
                    'success': False,
                    'error': str(e),
                    'stderr': str(e)
                }
                deployment['status'] = 'failed'
                deployment['error'] = f'Nginx configuration failed: {str(e)}'
                deployment['end_time'] = time.time()
                return deployment

        # Step 6: Create systemd service
        deployment['steps'].append({'name': 'Systemd service', 'status': 'in_progress'})

        try:
            # Get port from shared ports configuration
            port = get_port(bot_name)
            if not port:
                raise ValueError(f"No port configured for {bot_name} in shared/config/ports.yaml")

            # All bots now use TCP ports (no more Unix sockets)
            bind_config = f"0.0.0.0:{port}"

            service_config = self._load_template(
                'gunicorn.service.template',
                bot_name=bot_name,
                bot_name_title=bot_name.title(),
                description=description,
                bot_path=path,
                repo_path=repo_path,
                workers=workers,
                bind_config=bind_config
            )

            # Escape quotes for shell
            service_config_escaped = service_config.replace("'", "'\\''")

            # Write service file and reload systemd
            service_result = self._call_sally(
                server,
                f"echo '{service_config_escaped}' | {self._sudo('tee /etc/systemd/system/' + service_name + '.service')} > /dev/null && "
                f"{self._sudo('systemctl daemon-reload')} && "
                f"{self._sudo('systemctl enable ' + service_name)}"
            )

            deployment['steps'][-1]['status'] = 'completed' if service_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': service_result.get('success'),
                'stdout': service_result.get('stdout', ''),
                'stderr': service_result.get('stderr', ''),
                'exit_code': service_result.get('exit_code')
            }

            # Stop if systemd service creation failed
            if not service_result.get('success'):
                deployment['status'] = 'failed'
                error_parts = []
                if service_result.get('stderr'):
                    error_parts.append(f"stderr: {service_result['stderr']}")
                if service_result.get('stdout'):
                    error_parts.append(f"stdout: {service_result['stdout']}")
                if service_result.get('error'):
                    error_parts.append(f"error: {service_result['error']}")
                if service_result.get('exit_code') is not None:
                    error_parts.append(f"exit_code: {service_result['exit_code']}")
                error_details = ' | '.join(error_parts) if error_parts else 'No error details available'
                deployment['error'] = f"Systemd service creation failed: {error_details}"
                deployment['end_time'] = time.time()
                return deployment

        except Exception as e:
            deployment['steps'][-1]['status'] = 'failed'
            deployment['steps'][-1]['result'] = {
                'success': False,
                'error': str(e),
                'stderr': str(e)
            }
            deployment['status'] = 'failed'
            deployment['error'] = f'Systemd service creation failed: {str(e)}'
            deployment['end_time'] = time.time()
            return deployment

        # Step 7: SSL certificate (if configured and not skipping nginx)
        if ssl_email and not skip_nginx:
            deployment['steps'].append({'name': 'SSL certificate', 'status': 'in_progress'})

            ssl_result = self._call_sally(
                server,
                f"{self._sudo(f'certbot --nginx -d {domain} --non-interactive --agree-tos --email {ssl_email}')}",
                timeout=300
            )

            deployment['steps'][-1]['status'] = 'completed' if ssl_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': ssl_result.get('success'),
                'stdout': ssl_result.get('stdout', ''),
                'stderr': ssl_result.get('stderr', ''),
                'exit_code': ssl_result.get('exit_code')
            }

        # Step 8: Reload nginx (skip for internal-only bots)
        if not skip_nginx:
            deployment['steps'].append({'name': 'Reload nginx', 'status': 'in_progress'})

            reload_result = self._call_sally(server, self._sudo("systemctl reload nginx"))
            deployment['steps'][-1]['status'] = 'completed' if reload_result.get('success') else 'failed'
            deployment['steps'][-1]['result'] = {
                'success': reload_result.get('success'),
                'stdout': reload_result.get('stdout', ''),
                'stderr': reload_result.get('stderr', ''),
                'exit_code': reload_result.get('exit_code')
            }

        # Step 9: Manual configuration instructions (don't start service yet)
        deployment['steps'].append({'name': 'Manual configuration required', 'status': 'completed'})
        deployment['steps'][-1]['result'] = {
            'success': True,
            'message': f'Deployment setup complete! Before starting the service:\n'
                      f'1. SSH to the server: ssh {server}\n'
                      f'2. Edit configuration files:\n'
                      f'   - .env file: sudo nano {path}/.env (API keys, credentials, etc.)\n'
                      f'   - config.local.yaml: sudo nano {path}/config.local.yaml (servers, repo, domain, etc.)\n'
                      f'3. Start the service: sudo systemctl start {service_name}\n'
                      f'4. Check status: sudo systemctl status {service_name}\n'
                      f'5. View logs: sudo journalctl -u {service_name} -f'
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
        - Create config files from examples (.env, config.local.yaml)
        - Create nginx config
        - Create systemd service
        - Set up SSL with certbot (if ssl_email is configured)
        - Reload nginx
        - Provide instructions for manual configuration and service start

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

    def update_bot(self, server: str, bot_name: str) -> Dict:
        """
        Update a bot (simpler than full deploy)

        Just pulls latest code, installs dependencies, and restarts service.
        Use this for regular deployments after initial setup is complete.

        Args:
            server: Server name
            bot_name: Bot to update

        Returns:
            Update result with status
        """
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path')
        service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")

        update_result = {
            'bot': bot_name,
            'server': server,
            'steps': [],
            'success': True
        }

        # Step 1: Git pull
        update_result['steps'].append({'name': 'Pull latest code', 'status': 'in_progress'})
        if self.use_sudo:
            pull_cmd = f"cd {path} && sudo -u www-data /usr/bin/git pull"
        else:
            pull_cmd = f"cd {path} && git pull"

        pull_result = self._call_sally(server, pull_cmd)

        update_result['steps'][-1]['status'] = 'completed' if pull_result.get('success') else 'failed'
        update_result['steps'][-1]['result'] = pull_result

        if not pull_result.get('success'):
            update_result['success'] = False
            update_result['error'] = 'Failed to pull latest code'
            return update_result

        # Step 2: Restart service
        update_result['steps'].append({'name': 'Restart service', 'status': 'in_progress'})
        restart_result = self._call_sally(
            server,
            self._sudo(f"systemctl restart {service_name}")
        )

        update_result['steps'][-1]['status'] = 'completed' if restart_result.get('success') else 'failed'
        update_result['steps'][-1]['result'] = restart_result

        if not restart_result.get('success'):
            update_result['success'] = False
            update_result['error'] = 'Failed to restart service'
            return update_result

        return update_result

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
            self._sudo(f"certbot --nginx -d {domain} --non-interactive --agree-tos --email {email}"),
            timeout=300
        )

        return {
            'success': result.get('success'),
            'domain': domain,
            'output': result.get('stdout', ''),
            'error': result.get('stderr', '')
        }

    def teardown_bot(self, server: str, bot_name: str, remove_code: bool = False, remove_from_config: bool = False) -> Dict:
        """
        Remove/teardown a bot from the server

        Removes all deployment artifacts:
        - Stops and disables systemd service
        - Removes systemd service file
        - Removes nginx config (if applicable)
        - Reloads daemons
        - Optionally removes code directory
        - Optionally removes bot from config.local.yaml and restarts Dorothy

        Args:
            server: Server name
            bot_name: Bot to remove
            remove_code: Whether to also remove the code directory (default: False)
            remove_from_config: Whether to remove from config.local.yaml (default: False)

        Returns:
            Teardown result with status and removed_from_config flag
        """
        bot_config = config.get_bot_config(bot_name)
        if not bot_config:
            return {'success': False, 'error': f"Bot {bot_name} not configured"}

        path = bot_config.get('path')
        service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")
        skip_nginx = bot_config.get('skip_nginx', False)
        nginx_config_name = bot_config.get('nginx_config_name', bot_name)

        teardown_result = {
            'bot': bot_name,
            'server': server,
            'steps': [],
            'success': True
        }

        # Step 1: Stop and disable service
        teardown_result['steps'].append({'name': 'Stop and disable service', 'status': 'in_progress'})
        stop_result = self._call_sally(
            server,
            f"{self._sudo(f'systemctl stop {service_name}')} && {self._sudo(f'systemctl disable {service_name}')}"
        )
        teardown_result['steps'][-1]['status'] = 'completed' if stop_result.get('success') else 'failed'
        teardown_result['steps'][-1]['result'] = stop_result

        # Step 2: Remove systemd service file
        teardown_result['steps'].append({'name': 'Remove systemd service', 'status': 'in_progress'})
        remove_service_result = self._call_sally(
            server,
            f"{self._sudo(f'rm -f /etc/systemd/system/{service_name}.service')} && {self._sudo('systemctl daemon-reload')}"
        )
        teardown_result['steps'][-1]['status'] = 'completed' if remove_service_result.get('success') else 'failed'
        teardown_result['steps'][-1]['result'] = remove_service_result

        # Step 3: Remove nginx config (if applicable)
        if not skip_nginx:
            teardown_result['steps'].append({'name': 'Remove nginx config', 'status': 'in_progress'})
            remove_nginx_result = self._call_sally(
                server,
                f"{self._sudo(f'rm -f /etc/nginx/sites-enabled/{nginx_config_name}')} && "
                f"{self._sudo(f'rm -f /etc/nginx/sites-available/{nginx_config_name}')} && "
                f"{self._sudo('nginx -t')} && {self._sudo('systemctl reload nginx')}"
            )
            teardown_result['steps'][-1]['status'] = 'completed' if remove_nginx_result.get('success') else 'failed'
            teardown_result['steps'][-1]['result'] = remove_nginx_result

        # Step 4: Remove code directory (optional)
        if remove_code:
            teardown_result['steps'].append({'name': 'Remove code directory', 'status': 'in_progress'})
            remove_code_result = self._call_sally(
                server,
                self._sudo(f"rm -rf {path}")
            )
            teardown_result['steps'][-1]['status'] = 'completed' if remove_code_result.get('success') else 'failed'
            teardown_result['steps'][-1]['result'] = remove_code_result

        # Step 5: Remove from config.local.yaml (optional)
        teardown_result['removed_from_config'] = False
        if remove_from_config:
            teardown_result['steps'].append({'name': 'Remove from config and restart Dorothy', 'status': 'in_progress'})

            config_path = "/var/www/bot-team/dorothy/config.local.yaml"

            # Read current config
            read_result = self._call_sally(server, f"cat {config_path} 2>/dev/null || echo ''")

            if read_result.get('success'):
                current_config = read_result.get('stdout', '')

                # Remove bot section from YAML (simple approach - remove from bot name to next bot or end of bots section)
                import re
                # Pattern matches the bot entry and all its properties
                pattern = rf"^\s*{re.escape(bot_name)}:.*?(?=^\s*\w+:|^\w+:|$)"
                new_config = re.sub(pattern, '', current_config, flags=re.MULTILINE | re.DOTALL)

                # Write updated config
                escaped_config = new_config.replace("'", "'\\''")
                write_result = self._call_sally(
                    server,
                    f"echo '{escaped_config}' | {self._sudo(f'tee {config_path}')} > /dev/null"
                )

                if write_result.get('success'):
                    # Restart Dorothy
                    dorothy_config = config.get_bot_config('dorothy')
                    dorothy_service = dorothy_config.get('service', 'gunicorn-bot-team-dorothy')
                    restart_result = self._call_sally(server, self._sudo(f"systemctl restart {dorothy_service}"))

                    if restart_result.get('success'):
                        teardown_result['steps'][-1]['status'] = 'completed'
                        teardown_result['removed_from_config'] = True
                    else:
                        teardown_result['steps'][-1]['status'] = 'failed'
                        teardown_result['steps'][-1]['result'] = restart_result
                else:
                    teardown_result['steps'][-1]['status'] = 'failed'
                    teardown_result['steps'][-1]['result'] = write_result
            else:
                teardown_result['steps'][-1]['status'] = 'failed'
                teardown_result['steps'][-1]['result'] = read_result

        # Check if any steps failed
        teardown_result['success'] = all(
            step['status'] == 'completed' for step in teardown_result['steps']
        )

        return teardown_result

    def get_deployment_status(self, deployment_id: str) -> Optional[Dict]:
        """Get status of a deployment"""
        return self.deployments.get(deployment_id)

    def get_verification_status(self, verification_id: str) -> Optional[Dict]:
        """Get status of a verification"""
        return self.verifications.get(verification_id)

# Global instance
deployment_orchestrator = DeploymentOrchestrator()
