from flask import Blueprint, request, jsonify
from services.deployment_orchestrator import deployment_orchestrator
from config import config

api_bp = Blueprint('api', __name__)

@api_bp.route('/bots', methods=['GET'])
def list_bots():
    """List all configured bots"""
    bots = config.bots
    bot_list = []

    for name in bots.keys():
        # Get full bot config with defaults applied
        bot_config = config.get_bot_config(name)
        bot_list.append({
            'name': name,
            'port': bot_config.get('port'),
            'domain': bot_config.get('domain'),
            'path': bot_config.get('path'),
            'service': bot_config.get('service'),
            'workers': bot_config.get('workers'),
            'description': bot_config.get('description')
        })

    return jsonify({
        'bots': bot_list,
        'count': len(bot_list)
    })

@api_bp.route('/verify/<bot_name>', methods=['POST'])
def verify_bot(bot_name):
    """
    Verify a bot's deployment on a server

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    result = deployment_orchestrator.verify_deployment(server, bot_name)
    return jsonify(result)

@api_bp.route('/plan/<bot_name>', methods=['POST'])
def get_deployment_plan(bot_name):
    """
    Get deployment plan (dry-run) - shows what would be executed

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    plan = deployment_orchestrator.get_deployment_plan(server, bot_name)
    return jsonify(plan)

@api_bp.route('/deploy/<bot_name>', methods=['POST'])
def deploy_bot(bot_name):
    """
    Deploy a bot to a server

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    result = deployment_orchestrator.deploy_bot(server, bot_name)
    return jsonify(result)

@api_bp.route('/deployments', methods=['GET'])
def list_deployments():
    """List all deployment history"""
    deployments = list(deployment_orchestrator.deployments.values())
    deployments.reverse()  # Most recent first

    return jsonify({
        'deployments': deployments,
        'total': len(deployments)
    })

@api_bp.route('/deployments/<deployment_id>', methods=['GET'])
def get_deployment(deployment_id):
    """Get details of a specific deployment"""
    deployment = deployment_orchestrator.get_deployment_status(deployment_id)

    if not deployment:
        return jsonify({'error': 'Deployment not found'}), 404

    return jsonify(deployment)

@api_bp.route('/verifications/<verification_id>', methods=['GET'])
def get_verification(verification_id):
    """Get status of a verification"""
    verification = deployment_orchestrator.get_verification_status(verification_id)

    if not verification:
        return jsonify({'error': 'Verification not found'}), 404

    return jsonify(verification)

@api_bp.route('/health-check/<bot_name>', methods=['POST'])
def health_check_bot(bot_name):
    """
    Check if a bot is running and responding

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    bot_config = config.get_bot_config(bot_name)
    domain = bot_config.get('domain')
    skip_nginx = bot_config.get('skip_nginx', False)
    port = bot_config.get('port')

    # For internal-only bots, check direct port access or systemd service
    if skip_nginx:
        if port:
            # Try direct access via localhost:port
            result = deployment_orchestrator._call_sally(
                server,
                f"curl -s http://localhost:{port}/health || echo 'not responding'"
            )
            is_healthy = 'healthy' in result.get('stdout', '')

            return jsonify({
                'bot': bot_name,
                'server': server,
                'port': port,
                'access_method': 'direct_port',
                'healthy': is_healthy,
                'response': result.get('stdout', ''),
                'success': result.get('success')
            })
        else:
            # Fall back to checking systemd service status
            service_name = bot_config.get('service', f"gunicorn-{bot_name}")
            result = deployment_orchestrator._call_sally(
                server,
                f"sudo systemctl is-active {service_name}"
            )
            is_active = 'active' in result.get('stdout', '')

            return jsonify({
                'bot': bot_name,
                'server': server,
                'service': service_name,
                'access_method': 'systemd_service',
                'healthy': is_active,
                'response': result.get('stdout', ''),
                'success': result.get('success')
            })

    # For nginx-routed bots, check via domain (follow redirects for HTTPS)
    result = deployment_orchestrator._call_sally(
        server,
        f"curl -sL http://localhost/health -H 'Host: {domain}' || echo 'not responding'"
    )

    is_healthy = 'healthy' in result.get('stdout', '')

    return jsonify({
        'bot': bot_name,
        'server': server,
        'domain': domain,
        'access_method': 'nginx_domain',
        'healthy': is_healthy,
        'response': result.get('stdout', ''),
        'success': result.get('success')
    })

@api_bp.route('/start-service/<bot_name>', methods=['POST'])
def start_service(bot_name):
    """
    Start the systemd service for a bot

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    bot_config = config.get_bot_config(bot_name)
    service_name = bot_config.get('service', f"gunicorn-bot-team-{bot_name}")

    result = deployment_orchestrator._call_sally(
        server,
        f"sudo systemctl start {service_name}"
    )

    return jsonify({
        'success': result.get('success'),
        'service': service_name,
        'stdout': result.get('stdout', ''),
        'stderr': result.get('stderr', ''),
        'exit_code': result.get('exit_code')
    })

@api_bp.route('/add-bot', methods=['POST'])
def add_bot():
    """
    Add a new bot to config.local.yaml and restart Dorothy

    Body:
        name: Bot name (required)
        domain: Domain name (required)
        port: Port number (optional - if provided, nginx is skipped for internal-only bot)
        workers: Number of workers (optional, default: 2)
        description: Bot description (optional)
        server: Server name (optional, uses default)

    Note: skip_nginx is automatically determined by port presence (port provided = skip nginx)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    # Required fields
    bot_name = data.get('name')
    domain = data.get('domain')

    if not bot_name:
        return jsonify({'error': 'Bot name is required'}), 400

    if not domain:
        return jsonify({'error': 'Domain is required'}), 400

    # Optional fields
    port = data.get('port')
    workers = data.get('workers', 2)
    description = data.get('description', '')

    # Automatically determine skip_nginx based on port presence
    # If port is provided -> internal-only bot (skip nginx)
    # If port is not provided -> public bot (use nginx)
    skip_nginx = bool(port)

    # Build YAML snippet for new bot
    bot_yaml = f"""
  {bot_name}:"""

    if port:
        bot_yaml += f"\n    port: {port}"

    if domain:
        bot_yaml += f"\n    domain: {domain}"
    if workers != 2:
        bot_yaml += f"\n    workers: {workers}"
    if description:
        bot_yaml += f"\n    description: {description}"
    if skip_nginx:
        bot_yaml += f"\n    skip_nginx: true"

    # Path to config.local.yaml
    config_path = "/var/www/bot-team/dorothy/config.local.yaml"

    # Read current config
    read_result = deployment_orchestrator._call_sally(
        server,
        f"cat {config_path} 2>/dev/null || echo ''"
    )

    current_config = read_result.get('stdout', '').strip()

    # Check if bots section exists
    if 'bots:' not in current_config:
        # No bots section yet, create it
        new_config = current_config + f"\n\nbots:{bot_yaml}\n"
    else:
        # Append to existing bots section
        new_config = current_config + f"{bot_yaml}\n"

    # Write updated config (escape single quotes for shell)
    escaped_config = new_config.replace("'", "'\\''")
    write_result = deployment_orchestrator._call_sally(
        server,
        f"echo '{escaped_config}' | sudo tee {config_path} > /dev/null && sudo chown www-data:www-data {config_path}"
    )

    if not write_result.get('success'):
        return jsonify({
            'success': False,
            'error': 'Failed to write config file',
            'details': write_result
        }), 500

    # Restart Dorothy to load new config
    bot_config = config.get_bot_config('dorothy')
    service_name = bot_config.get('service', 'gunicorn-bot-team-dorothy')

    restart_result = deployment_orchestrator._call_sally(
        server,
        f"sudo systemctl restart {service_name}"
    )

    return jsonify({
        'success': True,
        'bot_name': bot_name,
        'message': 'Bot added successfully. Dorothy is restarting...',
        'restart_result': restart_result
    })

@api_bp.route('/restart-dorothy', methods=['POST'])
def restart_dorothy():
    """
    Restart Dorothy's own service (to reload config changes)

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    # Get Dorothy's service name from config
    bot_config = config.get_bot_config('dorothy')
    service_name = bot_config.get('service', 'gunicorn-bot-team-dorothy')

    result = deployment_orchestrator._call_sally(
        server,
        f"sudo systemctl restart {service_name}"
    )

    return jsonify({
        'success': result.get('success'),
        'service': service_name,
        'stdout': result.get('stdout', ''),
        'stderr': result.get('stderr', ''),
        'exit_code': result.get('exit_code')
    })

@api_bp.route('/update/<bot_name>', methods=['POST'])
def update_bot(bot_name):
    """
    Update a bot (simpler than full deploy - just pull code and restart)

    Body:
        server: Server name (optional, uses default)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    result = deployment_orchestrator.update_bot(server, bot_name)
    return jsonify(result)

@api_bp.route('/teardown/<bot_name>', methods=['POST'])
def teardown_bot(bot_name):
    """
    Remove/teardown a bot from the server

    Body:
        server: Server name (optional, uses default)
        remove_code: Whether to also remove code directory (optional, default: false)
        remove_from_config: Whether to remove bot from config.local.yaml (optional, default: false)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)
    remove_code = data.get('remove_code', False)
    remove_from_config = data.get('remove_from_config', False)

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    result = deployment_orchestrator.teardown_bot(server, bot_name, remove_code, remove_from_config)
    return jsonify(result)

@api_bp.route('/setup-ssl/<bot_name>', methods=['POST'])
def setup_ssl(bot_name):
    """
    Set up SSL certificate with certbot

    Body:
        server: Server name (optional, uses default)
        email: Email for Let's Encrypt (required)
    """
    data = request.get_json() or {}
    server = data.get('server', config.default_server)
    email = data.get('email')

    if not email:
        return jsonify({
            'error': 'Email is required for SSL setup'
        }), 400

    if bot_name not in config.bots:
        return jsonify({
            'error': f"Bot '{bot_name}' not configured"
        }), 404

    result = deployment_orchestrator.setup_ssl(server, bot_name, email)
    return jsonify(result)
