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
