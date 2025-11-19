"""API endpoints for bot deployment configuration."""
from flask import Blueprint, jsonify, request
from ..services.database import db
from shared.auth.bot_api import api_key_required

deployment_bp = Blueprint('deployment', __name__)


@deployment_bp.route('/deployment/bots', methods=['GET'])
@api_key_required
def get_all_deployment_configs():
    """Get deployment configuration for all bots."""
    bots = db.get_all_bots()

    return jsonify({
        'success': True,
        'count': len(bots),
        'bots': bots
    })


@deployment_bp.route('/deployment/bots/<bot_name>', methods=['GET'])
@api_key_required
def get_bot_deployment_config(bot_name):
    """Get deployment configuration for a specific bot."""
    config = db.get_bot_deployment_config(bot_name)

    if not config:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found'
        }), 404

    return jsonify({
        'success': True,
        'bot': config
    })


@deployment_bp.route('/deployment/bots', methods=['POST'])
@api_key_required
def create_bot():
    """Create a new bot entry."""
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    required_fields = ['name', 'description', 'port']
    missing_fields = [f for f in required_fields if f not in data]

    if missing_fields:
        return jsonify({
            'success': False,
            'error': f'Missing required fields: {", ".join(missing_fields)}'
        }), 400

    try:
        bot_id = db.add_bot(**data)

        if bot_id:
            bot = db.get_bot(data['name'])
            return jsonify({
                'success': True,
                'message': f'Bot {data["name"]} created successfully',
                'bot': bot
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create bot'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deployment_bp.route('/deployment/bots/<bot_name>', methods=['PUT', 'PATCH'])
@api_key_required
def update_bot(bot_name):
    """Update a bot's deployment configuration."""
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    # Check if bot exists
    existing = db.get_bot(bot_name)
    if not existing:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found'
        }), 404

    try:
        success = db.update_bot(bot_name, **data)

        if success:
            bot = db.get_bot(bot_name)
            return jsonify({
                'success': True,
                'message': f'Bot {bot_name} updated successfully',
                'bot': bot
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No changes made'
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deployment_bp.route('/deployment/bots/<bot_name>', methods=['DELETE'])
@api_key_required
def delete_bot(bot_name):
    """Delete a bot from the registry."""
    # Check if bot exists
    existing = db.get_bot(bot_name)
    if not existing:
        return jsonify({
            'success': False,
            'error': f'Bot {bot_name} not found'
        }), 404

    try:
        success = db.delete_bot(bot_name)

        if success:
            return jsonify({
                'success': True,
                'message': f'Bot {bot_name} deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete bot'
            }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@deployment_bp.route('/deployment/defaults', methods=['GET'])
@api_key_required
def get_deployment_defaults():
    """Get deployment defaults/templates."""
    defaults = db.get_deployment_defaults()

    return jsonify({
        'success': True,
        'defaults': defaults
    })


@deployment_bp.route('/deployment/defaults', methods=['PUT', 'PATCH'])
@api_key_required
def update_deployment_defaults():
    """Update deployment defaults/templates."""
    data = request.get_json()

    if not data:
        return jsonify({
            'success': False,
            'error': 'Request body is required'
        }), 400

    try:
        success = db.update_deployment_defaults(**data)

        if success:
            defaults = db.get_deployment_defaults()
            return jsonify({
                'success': True,
                'message': 'Deployment defaults updated successfully',
                'defaults': defaults
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No valid fields to update'
            }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
