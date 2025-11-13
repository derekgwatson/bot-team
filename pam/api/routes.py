from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)

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
