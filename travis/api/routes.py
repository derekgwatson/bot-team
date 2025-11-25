"""
Travis API Routes
Handles location pings, staff management, and journey tracking
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, request, jsonify
from datetime import datetime
import logging

from travis.config import config
from travis.database.db import db

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ══════════════════════════════════════════════════════════════════════════════
# Location endpoints (called by mobile app)
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/location', methods=['POST'])
def record_location():
    """
    Record a location ping from a device.
    This is the main endpoint called by the iOS app.

    Request headers:
        X-Device-Token: <device_token>

    Request JSON:
        {
            "latitude": -35.2809,
            "longitude": 149.1300,
            "accuracy": 10.0,           // optional, meters
            "heading": 180.0,           // optional, degrees
            "speed": 15.5,              // optional, m/s
            "altitude": 580.0,          // optional, meters
            "battery_level": 85.0,      // optional, percentage
            "timestamp": "2025-..."     // optional, ISO format
        }

    Response JSON:
        {
            "success": true,
            "ping_id": 123,
            "message": "Location recorded"
        }
    """
    try:
        # Authenticate via device token
        device_token = request.headers.get('X-Device-Token')
        if not device_token:
            data = request.get_json() or {}
            device_token = data.get('device_token')

        if not device_token:
            return jsonify({
                'success': False,
                'error': 'device_token is required (X-Device-Token header or JSON body)'
            }), 401

        staff = db.get_staff_by_token(device_token)
        if not staff:
            return jsonify({
                'success': False,
                'error': 'Invalid device_token'
            }), 401

        # Get location data
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if latitude is None or longitude is None:
            return jsonify({
                'success': False,
                'error': 'latitude and longitude are required'
            }), 400

        # Parse optional timestamp
        timestamp = None
        if data.get('timestamp'):
            try:
                timestamp = datetime.fromisoformat(
                    data['timestamp'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                pass

        # Get active journey if any
        active_journey = db.get_active_journey(staff['id'])
        journey_id = active_journey['id'] if active_journey else None

        # Record the ping
        ping_id = db.record_ping(
            staff_id=staff['id'],
            latitude=float(latitude),
            longitude=float(longitude),
            journey_id=journey_id,
            accuracy=data.get('accuracy'),
            heading=data.get('heading'),
            speed=data.get('speed'),
            altitude=data.get('altitude'),
            battery_level=data.get('battery_level'),
            timestamp=timestamp
        )

        # Log if configured
        if config.log_pings or logger.isEnabledFor(logging.DEBUG):
            logger.info(
                f"Location ping: staff={staff['name']} ({staff['id']}), "
                f"lat={latitude}, lng={longitude}, journey={journey_id}, ping_id={ping_id}"
            )

        return jsonify({
            'success': True,
            'ping_id': ping_id,
            'message': 'Location recorded'
        }), 200

    except Exception as e:
        logger.error(f"Location ping error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/location/<int:staff_id>', methods=['GET'])
def get_location(staff_id: int):
    """
    Get shareable location for a staff member.
    This is the endpoint called by Journey bot to get location for customers.

    Privacy logic:
    - Only returns coordinates when staff is 'in_transit'
    - When 'at_customer', returns message "with previous customer"
    - When 'off_duty' or 'on_break', returns not active message

    Response JSON (when shareable):
        {
            "success": true,
            "shareable": true,
            "status": "in_transit",
            "latitude": -35.2809,
            "longitude": 149.1300,
            "heading": 180.0,
            "speed": 15.5,
            "timestamp": "2025-..."
        }

    Response JSON (when not shareable):
        {
            "success": true,
            "shareable": false,
            "status": "at_customer",
            "message": "Currently with previous customer"
        }
    """
    try:
        location_data = db.get_shareable_location(staff_id)

        if 'error' in location_data:
            return jsonify({
                'success': False,
                'error': location_data['error']
            }), 404

        return jsonify({
            'success': True,
            **location_data
        }), 200

    except Exception as e:
        logger.error(f"Get location error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# ══════════════════════════════════════════════════════════════════════════════
# Staff endpoints
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/staff', methods=['GET'])
def list_staff():
    """
    List all staff members

    Response JSON:
        {
            "success": true,
            "staff": [...]
        }
    """
    try:
        staff = db.get_all_staff()
        # Don't expose device tokens in list
        for s in staff:
            s.pop('device_token', None)

        return jsonify({
            'success': True,
            'staff': staff
        }), 200

    except Exception as e:
        logger.error(f"List staff error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/staff', methods=['POST'])
def create_staff():
    """
    Create a new staff member

    Request JSON:
        {
            "name": "Sarah Jones",
            "email": "sarah@company.com"
        }

    Response JSON:
        {
            "success": true,
            "staff": {
                "id": 1,
                "name": "Sarah Jones",
                "email": "sarah@company.com",
                "device_token": "abc123..."  // Save this for mobile app!
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

        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()

        if not name:
            return jsonify({
                'success': False,
                'error': 'name is required'
            }), 400

        if not email:
            return jsonify({
                'success': False,
                'error': 'email is required'
            }), 400

        # Check if email already exists
        existing = db.get_staff_by_email(email)
        if existing:
            return jsonify({
                'success': False,
                'error': 'Staff with this email already exists'
            }), 409

        staff = db.create_staff(name=name, email=email)

        logger.info(f"Created staff: {name} ({email})")

        return jsonify({
            'success': True,
            'staff': staff,
            'message': 'Staff created. Save the device_token for mobile app configuration!'
        }), 201

    except Exception as e:
        logger.error(f"Create staff error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/staff/<int:staff_id>', methods=['GET'])
def get_staff(staff_id: int):
    """
    Get staff member details

    Response JSON:
        {
            "success": true,
            "staff": {...}
        }
    """
    try:
        staff = db.get_staff_by_id(staff_id)
        if not staff:
            return jsonify({
                'success': False,
                'error': 'Staff not found'
            }), 404

        # Don't expose device token
        staff.pop('device_token', None)

        return jsonify({
            'success': True,
            'staff': staff
        }), 200

    except Exception as e:
        logger.error(f"Get staff error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/staff/<int:staff_id>/status', methods=['PUT'])
def update_status(staff_id: int):
    """
    Update staff member's status.
    Called by mobile app when status changes.

    Request headers:
        X-Device-Token: <device_token>

    Request JSON:
        {
            "status": "in_transit"  // off_duty, in_transit, at_customer, on_break
        }

    Response JSON:
        {
            "success": true,
            "message": "Status updated to in_transit"
        }
    """
    try:
        # Can authenticate via device token or allow admin access
        device_token = request.headers.get('X-Device-Token')

        if device_token:
            staff = db.get_staff_by_token(device_token)
            if not staff or staff['id'] != staff_id:
                return jsonify({
                    'success': False,
                    'error': 'Invalid device_token or staff_id mismatch'
                }), 401
        else:
            # Allow without token for admin/bot-to-bot calls
            staff = db.get_staff_by_id(staff_id)
            if not staff:
                return jsonify({
                    'success': False,
                    'error': 'Staff not found'
                }), 404

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        status = data.get('status', '').strip().lower()

        if status not in config.status_values:
            return jsonify({
                'success': False,
                'error': f'Invalid status. Must be one of: {", ".join(config.status_values)}'
            }), 400

        db.update_staff_status(staff_id, status)
        logger.info(f"Staff {staff['name']} ({staff_id}) status changed to {status}")

        return jsonify({
            'success': True,
            'message': f'Status updated to {status}'
        }), 200

    except Exception as e:
        logger.error(f"Update status error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/staff/<int:staff_id>/token', methods=['POST'])
def regenerate_token(staff_id: int):
    """
    Regenerate device token for a staff member.
    Use this if a device is lost or token is compromised.

    Response JSON:
        {
            "success": true,
            "device_token": "new_token_here",
            "message": "Token regenerated. Update the mobile app!"
        }
    """
    try:
        staff = db.get_staff_by_id(staff_id)
        if not staff:
            return jsonify({
                'success': False,
                'error': 'Staff not found'
            }), 404

        new_token = db.regenerate_device_token(staff_id)
        logger.info(f"Regenerated token for staff {staff['name']} ({staff_id})")

        return jsonify({
            'success': True,
            'device_token': new_token,
            'message': 'Token regenerated. Update the mobile app with the new token!'
        }), 200

    except Exception as e:
        logger.error(f"Regenerate token error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# ══════════════════════════════════════════════════════════════════════════════
# Journey endpoints
# ══════════════════════════════════════════════════════════════════════════════

@api_bp.route('/journeys', methods=['POST'])
def create_journey():
    """
    Create a new journey for a staff member

    Request JSON:
        {
            "staff_id": 1,
            "job_reference": "JOB-12345",     // optional
            "customer_name": "Mrs. Jones",    // optional
            "customer_address": "123 Main St", // optional
            "customer_lat": -35.2809,         // optional, for geofencing
            "customer_lng": 149.1300          // optional, for geofencing
        }

    Response JSON:
        {
            "success": true,
            "journey": {...}
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        staff_id = data.get('staff_id')
        if not staff_id:
            return jsonify({
                'success': False,
                'error': 'staff_id is required'
            }), 400

        # Verify staff exists
        staff = db.get_staff_by_id(staff_id)
        if not staff:
            return jsonify({
                'success': False,
                'error': 'Staff not found'
            }), 404

        journey = db.create_journey(
            staff_id=staff_id,
            job_reference=data.get('job_reference'),
            customer_name=data.get('customer_name'),
            customer_address=data.get('customer_address'),
            customer_lat=data.get('customer_lat'),
            customer_lng=data.get('customer_lng')
        )

        return jsonify({
            'success': True,
            'journey': journey
        }), 201

    except Exception as e:
        logger.error(f"Create journey error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/<int:journey_id>', methods=['GET'])
def get_journey(journey_id: int):
    """
    Get journey details

    Response JSON:
        {
            "success": true,
            "journey": {...}
        }
    """
    try:
        journey = db.get_journey_by_id(journey_id)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        return jsonify({
            'success': True,
            'journey': journey
        }), 200

    except Exception as e:
        logger.error(f"Get journey error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/<int:journey_id>/start', methods=['PUT'])
def start_journey(journey_id: int):
    """
    Start a journey (mark as in_progress).
    Also sets staff status to 'in_transit'.

    Response JSON:
        {
            "success": true,
            "message": "Journey started"
        }
    """
    try:
        journey = db.get_journey_by_id(journey_id)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        if journey['status'] != 'pending':
            return jsonify({
                'success': False,
                'error': f"Cannot start journey with status '{journey['status']}'"
            }), 400

        db.start_journey(journey_id)
        db.update_staff_status(journey['staff_id'], 'in_transit')

        logger.info(f"Journey {journey_id} started for staff {journey['staff_id']}")

        return jsonify({
            'success': True,
            'message': 'Journey started'
        }), 200

    except Exception as e:
        logger.error(f"Start journey error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/<int:journey_id>/arrive', methods=['PUT'])
def arrive_journey(journey_id: int):
    """
    Mark journey as arrived.
    Also sets staff status to 'at_customer'.

    Response JSON:
        {
            "success": true,
            "message": "Arrival recorded"
        }
    """
    try:
        journey = db.get_journey_by_id(journey_id)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        if journey['status'] != 'in_progress':
            return jsonify({
                'success': False,
                'error': f"Cannot mark arrived for journey with status '{journey['status']}'"
            }), 400

        db.arrive_journey(journey_id)
        db.update_staff_status(journey['staff_id'], 'at_customer')

        logger.info(f"Journey {journey_id} arrived for staff {journey['staff_id']}")

        return jsonify({
            'success': True,
            'message': 'Arrival recorded'
        }), 200

    except Exception as e:
        logger.error(f"Arrive journey error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/<int:journey_id>/complete', methods=['PUT'])
def complete_journey(journey_id: int):
    """
    Mark journey as completed.
    Sets staff status to 'off_duty' (or they can start another journey).

    Response JSON:
        {
            "success": true,
            "message": "Journey completed"
        }
    """
    try:
        journey = db.get_journey_by_id(journey_id)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        db.complete_journey(journey_id)
        # Don't automatically set off_duty - they might have another appointment

        logger.info(f"Journey {journey_id} completed for staff {journey['staff_id']}")

        return jsonify({
            'success': True,
            'message': 'Journey completed'
        }), 200

    except Exception as e:
        logger.error(f"Complete journey error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/<int:journey_id>/pings', methods=['GET'])
def get_journey_pings(journey_id: int):
    """
    Get all location pings for a journey (for drawing the route).

    Query params:
        limit: Maximum pings to return (default 1000)

    Response JSON:
        {
            "success": true,
            "pings": [...]
        }
    """
    try:
        journey = db.get_journey_by_id(journey_id)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        limit = request.args.get('limit', 1000, type=int)
        pings = db.get_journey_pings(journey_id, limit)

        return jsonify({
            'success': True,
            'pings': pings
        }), 200

    except Exception as e:
        logger.error(f"Get journey pings error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/journeys/by-reference/<job_reference>', methods=['GET'])
def get_journey_by_reference(job_reference: str):
    """
    Get journey by external job reference

    Response JSON:
        {
            "success": true,
            "journey": {...}
        }
    """
    try:
        journey = db.get_journey_by_job_reference(job_reference)
        if not journey:
            return jsonify({
                'success': False,
                'error': 'Journey not found'
            }), 404

        return jsonify({
            'success': True,
            'journey': journey
        }), 200

    except Exception as e:
        logger.error(f"Get journey by reference error: {e}", exc_info=True)
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
        'personality': 'Watchful and discreet, tracks locations while respecting privacy',
        'capabilities': [
            'Receive GPS location pings from field staff devices',
            'Track staff status (at_customer, in_transit, off_duty)',
            'Privacy-aware location sharing (only share when in transit)',
            'Store location history for active journeys',
            'Provide location API for Journey bot'
        ],
        'privacy_note': 'Tracker only shares exact coordinates when staff is in_transit. '
                        'When at another customer, only indicates "with previous customer" to protect privacy.'
    })
