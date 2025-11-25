"""
Juno API Routes
Handles tracking link creation and management
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, request, jsonify
import requests
import logging

from juno.config import config
from juno.database.db import db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ══════════════════════════════════════════════════════════════════════════════
# Tracking link endpoints
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/tracking-links', methods=['POST'])
def create_tracking_link():
    """
    Create a new tracking link for a customer.
    Call this when you want to send a customer their tracking link.

    Request JSON:
        {
            "journey_id": 1,                    // required - Travis journey ID
            "staff_id": 1,                      // required - Travis staff ID
            "customer_name": "Mrs. Jones",      // optional
            "customer_phone": "+61412345678",   // optional
            "customer_email": "jones@email.com", // optional
            "destination_address": "123 Main St", // optional
            "destination_lat": -35.2809,        // optional
            "destination_lng": 149.1300         // optional
        }

    Response JSON:
        {
            "success": true,
            "tracking_link": {
                "id": 1,
                "code": "abc123xyz789",
                "url": "http://localhost:8022/track/abc123xyz789",
                ...
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        journey_id = data.get('journey_id')
        staff_id = data.get('staff_id')

        if not journey_id:
            return jsonify({
                'success': False,
                'error': 'journey_id is required'
            }), 400

        if not staff_id:
            return jsonify({
                'success': False,
                'error': 'staff_id is required'
            }), 400

        # Create the tracking link
        link = db.create_tracking_link(
            journey_id=journey_id,
            staff_id=staff_id,
            customer_name=data.get('customer_name'),
            customer_phone=data.get('customer_phone'),
            customer_email=data.get('customer_email'),
            destination_address=data.get('destination_address'),
            destination_lat=data.get('destination_lat'),
            destination_lng=data.get('destination_lng'),
            expiry_hours=config.link_expiry_hours,
            code_length=config.code_length
        )

        # Add the full URL
        link['url'] = f"http://localhost:{config.server_port}/track/{link['code']}"

        logger.info(f"Created tracking link {link['code']} for journey {journey_id}")

        return jsonify({
            'success': True,
            'tracking_link': link
        }), 201

    except Exception as e:
        logger.error(f"Create tracking link error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/tracking-links/<code>', methods=['GET'])
def get_tracking_link(code: str):
    """
    Get tracking link details by code

    Response JSON:
        {
            "success": true,
            "tracking_link": {...}
        }
    """
    try:
        link = db.get_tracking_link_by_code(code)
        if not link:
            return jsonify({
                'success': False,
                'error': 'Tracking link not found'
            }), 404

        return jsonify({
            'success': True,
            'tracking_link': link
        }), 200

    except Exception as e:
        logger.error(f"Get tracking link error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/tracking-links/<code>/location', methods=['GET'])
def get_tracking_location(code: str):
    """
    Get current location for a tracking link.
    This calls Travis to get the privacy-aware location.

    Response JSON (when in transit):
        {
            "success": true,
            "shareable": true,
            "status": "in_transit",
            "latitude": -35.2809,
            "longitude": 149.1300,
            "heading": 180.0,
            "speed": 15.5
        }

    Response JSON (when at previous customer):
        {
            "success": true,
            "shareable": false,
            "status": "at_customer",
            "message": "Currently with previous customer"
        }
    """
    try:
        # Get the tracking link
        link = db.get_tracking_link_by_code(code)
        if not link:
            return jsonify({
                'success': False,
                'error': 'Tracking link not found'
            }), 404

        # Check if link is still active
        if link['status'] != 'active':
            return jsonify({
                'success': False,
                'shareable': False,
                'status': link['status'],
                'message': f"Tracking session has ended ({link['status']})"
            }), 200

        # Record the view
        db.record_view(code)

        # Call Travis to get location
        try:
            response = requests.get(
                f"{config.travis_base_url}/api/location/{link['staff_id']}",
                timeout=5
            )

            if response.status_code == 200:
                location_data = response.json()
                return jsonify({
                    'success': True,
                    **location_data
                }), 200
            else:
                logger.warning(f"Travis returned {response.status_code} for staff {link['staff_id']}")
                return jsonify({
                    'success': False,
                    'shareable': False,
                    'message': 'Location temporarily unavailable'
                }), 200

        except requests.RequestException as e:
            logger.error(f"Failed to contact Travis: {e}")
            return jsonify({
                'success': False,
                'shareable': False,
                'message': 'Location service temporarily unavailable'
            }), 200

    except Exception as e:
        logger.error(f"Get tracking location error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/tracking-links/<code>/arrived', methods=['PUT'])
def mark_arrived(code: str):
    """
    Mark a tracking link as arrived.
    Called when the staff member arrives at the destination.

    Response JSON:
        {
            "success": true,
            "message": "Marked as arrived"
        }
    """
    try:
        link = db.get_tracking_link_by_code(code)
        if not link:
            return jsonify({
                'success': False,
                'error': 'Tracking link not found'
            }), 404

        db.mark_arrived(code)

        return jsonify({
            'success': True,
            'message': 'Marked as arrived'
        }), 200

    except Exception as e:
        logger.error(f"Mark arrived error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/tracking-links/<code>/cancel', methods=['PUT'])
def cancel_tracking_link(code: str):
    """
    Cancel a tracking link

    Response JSON:
        {
            "success": true,
            "message": "Tracking link cancelled"
        }
    """
    try:
        link = db.get_tracking_link_by_code(code)
        if not link:
            return jsonify({
                'success': False,
                'error': 'Tracking link not found'
            }), 404

        db.mark_cancelled(code)

        return jsonify({
            'success': True,
            'message': 'Tracking link cancelled'
        }), 200

    except Exception as e:
        logger.error(f"Cancel tracking link error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/tracking-links', methods=['GET'])
def list_active_links():
    """
    List all active tracking links (admin view)

    Response JSON:
        {
            "success": true,
            "tracking_links": [...]
        }
    """
    try:
        links = db.get_all_active_links()

        return jsonify({
            'success': True,
            'tracking_links': links
        }), 200

    except Exception as e:
        logger.error(f"List tracking links error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# ══════════════════════════════════════════════════════════════════════════════
# Bot intro endpoint
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    Bot introduction - personality and capabilities
    """
    return jsonify({
        'name': config.name.title(),
        'emoji': config.emoji,
        'personality': 'Warm and reassuring, keeps customers informed about their upcoming visit',
        'capabilities': [
            'Generate unique tracking links for customers',
            'Serve customer-facing map tracking page',
            'Display real-time location when staff is in transit',
            'Respect privacy - only shows "with previous customer" when appropriate',
            'Auto-expire tracking links after delivery'
        ],
        'integration': f'Juno calls Travis ({config.travis_base_url}) to get staff locations'
    })
