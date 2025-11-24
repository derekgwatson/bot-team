"""API endpoints for bot information and health checks."""
from flask import Blueprint, jsonify, request
from services.bot_service import bot_service
from services.database import db
from shared.auth.bot_api import api_key_required
import os
import yaml

bots_bp = Blueprint('bots', __name__)


@bots_bp.route('/bots', methods=['GET'])
@api_key_required
def get_all_bots():
    """Get information about all bots."""
    bots = bot_service.get_all_bots()
    return jsonify({
        'success': True,
        'bots': bots
    })


@bots_bp.route('/bots/<bot_name>', methods=['GET'])
@api_key_required
def get_bot(bot_name):
    """Get information about a specific bot."""
    bot_info = bot_service.get_bot_info(bot_name)

    if not bot_info:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found'
        }), 404

    # Add the bot's API URL to the response
    bot_url = bot_service.get_bot_url(bot_name)
    if bot_url:
        bot_info = bot_info.copy()  # Don't modify the original
        bot_info['url'] = bot_url

    return jsonify({
        'success': True,
        'bot': bot_info
    })


@bots_bp.route('/health/all', methods=['GET'])
@api_key_required
def check_all_health():
    """Check health of all bots."""
    results = bot_service.check_all_bots_health()

    # Summary stats
    healthy = sum(1 for r in results if r['status'] == 'healthy')
    total = len(results)

    return jsonify({
        'success': True,
        'summary': {
            'total': total,
            'healthy': healthy,
            'unhealthy': total - healthy
        },
        'results': results
    })


@bots_bp.route('/health/<bot_name>', methods=['GET'])
@api_key_required
def check_bot_health(bot_name):
    """Check health of a specific bot."""
    result = bot_service.check_bot_health(bot_name)

    return jsonify({
        'success': True,
        'health': result
    })


@bots_bp.route('/health/public/all', methods=['GET'])
@api_key_required
def check_public_bots_health():
    """Check health of only public-facing bots (for async loading)."""
    # Get public bots from database
    public_bots = db.get_public_bots()
    public_bot_names = [bot['name'] for bot in public_bots]

    # Check health for each public bot
    results = []
    for bot_name in public_bot_names:
        health = bot_service.check_bot_health(bot_name)
        results.append(health)

    return jsonify({
        'success': True,
        'results': results
    })


@bots_bp.route('/capabilities/<bot_name>', methods=['GET'])
@api_key_required
def get_bot_capabilities(bot_name):
    """Get capabilities of a specific bot."""
    capabilities = bot_service.get_bot_capabilities(bot_name)

    if capabilities is None:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found'
        }), 404

    return jsonify({
        'success': True,
        'bot': bot_name,
        'capabilities': capabilities
    })


@bots_bp.route('/search', methods=['GET'])
@api_key_required
def search_bots():
    """Search for bots by capability keyword."""
    keyword = request.args.get('q', '')

    if not keyword:
        return jsonify({
            'success': False,
            'error': 'Search query parameter "q" is required'
        }), 400

    results = bot_service.search_bots_by_capability(keyword)

    return jsonify({
        'success': True,
        'query': keyword,
        'results': results,
        'count': len(results)
    })


@bots_bp.route('/summary', methods=['GET'])
@api_key_required
def get_team_summary():
    """Get a summary of the bot team."""
    summary = bot_service.get_team_summary()

    return jsonify({
        'success': True,
        'summary': summary
    })


@bots_bp.route('/network', methods=['GET'])
@api_key_required
def get_network_data():
    """Get bot network data for visualization (nodes and edges)."""
    # Get the bot-team directory (parent of chester)
    chester_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bot_team_dir = os.path.dirname(chester_dir)

    nodes = []
    edges = []

    # Scan all bot directories
    for bot_name in os.listdir(bot_team_dir):
        bot_path = os.path.join(bot_team_dir, bot_name)
        config_path = os.path.join(bot_path, 'config.yaml')

        # Skip if not a directory or no config.yaml
        if not os.path.isdir(bot_path) or not os.path.exists(config_path):
            continue

        # Skip special directories
        if bot_name in ['shared', 'scripts', 'tests', 'monica-chrome-extension', '.git']:
            continue

        try:
            # Read the config file
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            if not config:
                continue

            # Extract bot info
            node = {
                'id': bot_name,
                'label': config.get('name', bot_name),
                'description': config.get('description', ''),
                'version': config.get('version', ''),
                'emoji': config.get('emoji', '🤖'),
                'personality': config.get('personality', '')
            }
            nodes.append(node)

            # Extract dependencies and create edges
            dependencies = config.get('dependencies', [])
            for dep in dependencies:
                # Dependencies can be "bot_name # comment" format
                dep_name = dep.split('#')[0].strip() if isinstance(dep, str) else dep
                edges.append({
                    'from': bot_name,
                    'to': dep_name
                })

        except Exception as e:
            # Skip bots with invalid configs
            print(f"Error reading config for {bot_name}: {e}")
            continue

    return jsonify({
        'success': True,
        'nodes': nodes,
        'edges': edges
    })
