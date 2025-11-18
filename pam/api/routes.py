from flask import Blueprint, jsonify, session, request

api_bp = Blueprint('api', __name__)

@api_bp.route('/dependencies', methods=['GET'])
def get_dependencies():
    """Get list of bots that Pam depends on"""
    return jsonify({
        'dependencies': ['peter', 'quinn']
    })

@api_bp.route('/dev-config', methods=['GET'])
def get_dev_config():
    """Get current dev bot configuration (from session)"""
    return jsonify(session.get('dev_bot_config', {}))

@api_bp.route('/dev-config', methods=['POST'])
def update_dev_config():
    """Update dev bot configuration (stores in session)"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Get existing config or create new
    dev_config = session.get('dev_bot_config', {})

    # Update with new settings
    dev_config.update(data)

    # Store in session
    session['dev_bot_config'] = dev_config

    return jsonify({
        'success': True,
        'config': dev_config
    })

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    GET /api/intro

    Returns Pam's introduction
    """
    return jsonify({
        'name': 'Pam',
        'greeting': "Hi! I'm Pam, your friendly phone directory.",
        'description': "I present the company phone directory in a beautiful, easy-to-use format. Think of me as your receptionist - I help you find anyone's contact information quickly. I get my data from Peter, who manages the directory behind the scenes.",
        'capabilities': [
            'Browse the phone directory in a beautiful card layout',
            'Search for people by name, position, or extension',
            'Quick access to phone numbers and email addresses',
            'Organized by department for easy navigation',
            'Click-to-call and click-to-email links'
        ]
    })
