"""API endpoints for bot information and health checks."""
from flask import Blueprint, jsonify, request
from services.bot_service import bot_service
from services.database import db
from shared.auth.bot_api import api_key_required

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
