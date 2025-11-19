from flask import Blueprint, jsonify, request
from services.google_reports import reports_service
from shared.auth.bot_api import api_key_required

api_bp = Blueprint('api', __name__)


@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """
    GET /api/intro

    Returns Iris's introduction
    """
    return jsonify({
        'name': 'Iris',
        'greeting': "Hi! I'm Iris, your Google Workspace reporting and analytics bot.",
        'description': "I keep an eye on how your Google Workspace is being used - storage quotas, usage patterns, and more. Need to know who's using the most space? Want to see Gmail vs Drive usage? I've got the insights you need. I work great with Fred too - he manages users, I tell you what they're up to!",
        'capabilities': [
            'Track storage usage per user (Gmail, Drive, total)',
            'View historical usage trends',
            'Identify users with high storage consumption',
            'Provide organization-wide storage analytics',
            'REST API for bot-to-bot integration',
            'Web dashboard for visual insights'
        ]
    })

@api_bp.route('/usage', methods=['GET'])
@api_key_required
def get_usage():
    """
    GET /api/usage

    Query parameters:
        - email: specific user email (optional)
        - date: YYYY-MM-DD format (optional, defaults to yesterday)

    Returns usage statistics
    """
    email = request.args.get('email')
    date = request.args.get('date')

    usage_data = reports_service.get_user_usage(email=email, date=date)

    if isinstance(usage_data, dict) and 'error' in usage_data:
        return jsonify(usage_data), 500

    return jsonify({
        'usage': usage_data,
        'count': len(usage_data)
    })

@api_bp.route('/usage/<email>', methods=['GET'])
@api_key_required
def get_user_usage(email):
    """
    GET /api/usage/<email>

    Returns usage statistics for a specific user
    """
    date = request.args.get('date')

    usage_data = reports_service.get_user_usage(email=email, date=date)

    if isinstance(usage_data, dict) and 'error' in usage_data:
        return jsonify(usage_data), 500

    if len(usage_data) == 0:
        return jsonify({'error': 'No usage data found for this user'}), 404

    return jsonify(usage_data[0])
