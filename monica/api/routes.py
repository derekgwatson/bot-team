"""
Monica API Routes
Handles device registration and heartbeat endpoints
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, request, jsonify
from datetime import datetime
import secrets
import logging

from monica.database.db import db
from monica.services.status_service import status_service
from monica.config import config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new device (with optional registration code for backward compatibility)

    Request JSON:
        {
            "registration_code": "ABC12345",  // optional if require_registration_codes is false
            "store_code": "FYSHWICK",
            "device_label": "Front Counter"
        }

    Response JSON:
        {
            "success": true,
            "device_id": 123,
            "agent_token": "abc123...",
            "message": "Device registered successfully"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        registration_code = data.get('registration_code', '').strip()
        store_code = data.get('store_code', '').strip()
        device_label = data.get('device_label', '').strip()

        if not store_code:
            return jsonify({
                'success': False,
                'error': 'store_code is required'
            }), 400

        if not device_label:
            return jsonify({
                'success': False,
                'error': 'device_label is required'
            }), 400

        # Check if registration codes are required (from config)
        require_codes = config.require_registration_codes

        if require_codes:
            # Secure mode - registration code required
            if not registration_code:
                return jsonify({
                    'success': False,
                    'error': 'registration_code is required'
                }), 400

            # Validate registration code
            code_data = db.get_registration_code(registration_code)
            if not code_data:
                return jsonify({
                    'success': False,
                    'error': 'Invalid, expired, or already used registration code'
                }), 403

            # Verify code matches the store and device
            if code_data['store_code'] != store_code or code_data['device_label'] != device_label:
                return jsonify({
                    'success': False,
                    'error': f"Registration code is for {code_data['store_code']}/{code_data['device_label']}"
                }), 403

        # Get or create store
        store_id = db.get_or_create_store(store_code)

        # Generate a secure agent token
        agent_token = secrets.token_urlsafe(32)

        # Get or create device
        device = db.get_or_create_device(store_id, device_label, agent_token)

        # Mark code as used if provided and required
        if require_codes and registration_code:
            db.mark_code_as_used(registration_code, device['id'])
            logger.info(
                f"Device registered with code {registration_code}: {store_code}/{device_label} "
                f"(device_id={device['id']})"
            )
        else:
            logger.info(
                f"Device registered (backward compatible mode): {store_code}/{device_label} "
                f"(device_id={device['id']})"
            )

        return jsonify({
            'success': True,
            'device_id': device['id'],
            'agent_token': device['agent_token'],
            'message': 'Device registered successfully'
        }), 200

    except Exception as e:
        logger.error(f"Registration error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    Record a heartbeat from a device

    Request headers:
        X-Agent-Token: <agent_token>

    Request JSON:
        {
            "timestamp": "2025-11-20T10:30:00Z",  # optional
            "latency_ms": 45.2,                    # optional
            "download_mbps": 98.5                  # optional
        }

    Response JSON:
        {
            "success": true,
            "message": "Heartbeat recorded"
        }
    """
    try:
        # Get agent token from header or JSON body
        agent_token = request.headers.get('X-Agent-Token')

        if not agent_token:
            data = request.get_json() or {}
            agent_token = data.get('agent_token')

        if not agent_token:
            return jsonify({
                'success': False,
                'error': 'agent_token is required (X-Agent-Token header or JSON body)'
            }), 401

        # Find device by token
        device = db.get_device_by_token(agent_token)
        if not device:
            return jsonify({
                'success': False,
                'error': 'Invalid agent_token'
            }), 401

        # Get request data
        data = request.get_json() or {}

        # Parse timestamp if provided
        timestamp = None
        if data.get('timestamp'):
            try:
                timestamp = datetime.fromisoformat(
                    data['timestamp'].replace('Z', '+00:00')
                )
            except (ValueError, AttributeError):
                pass

        # Get optional network metrics (convert to float if provided)
        latency_ms = data.get('latency_ms')
        if latency_ms is not None:
            try:
                latency_ms = float(latency_ms)
            except (ValueError, TypeError):
                latency_ms = None

        download_mbps = data.get('download_mbps')
        if download_mbps is not None:
            try:
                download_mbps = float(download_mbps)
            except (ValueError, TypeError):
                download_mbps = None

        # Get public IP from request
        # Check for X-Forwarded-For header (if behind proxy/nginx)
        public_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in public_ip:
            # X-Forwarded-For can contain multiple IPs, take the first one
            public_ip = public_ip.split(',')[0].strip()

        # Get user agent
        user_agent = request.headers.get('User-Agent', '')

        # Record heartbeat in database
        heartbeat_id = db.record_heartbeat(
            device_id=device['id'],
            public_ip=public_ip,
            user_agent=user_agent,
            latency_ms=latency_ms,
            download_mbps=download_mbps,
            timestamp=timestamp
        )

        # Compute status based on thresholds
        status = 'online'
        if latency_ms is not None and latency_ms > 500:
            status = 'degraded'
        elif download_mbps is not None and download_mbps < 10:
            status = 'degraded'

        # Update device's last heartbeat
        db.update_device_heartbeat(
            device_id=device['id'],
            status=status,
            public_ip=public_ip
        )

        logger.debug(
            f"Heartbeat recorded for device {device['id']} "
            f"(heartbeat_id={heartbeat_id})"
        )

        return jsonify({
            'success': True,
            'message': 'Heartbeat recorded'
        }), 200

    except Exception as e:
        logger.error(f"Heartbeat error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/devices', methods=['GET'])
def get_devices():
    """
    Get all devices with their current status

    Response JSON:
        {
            "success": true,
            "devices": [
                {
                    "id": 1,
                    "store_code": "FYSHWICK",
                    "device_label": "Front Counter",
                    "last_heartbeat_at": "2025-11-20T10:30:00",
                    "status": "online",
                    "public_ip": "203.123.45.67",
                    ...
                }
            ]
        }
    """
    try:
        devices = db.get_all_devices_with_stores()
        enriched = [status_service.enrich_device(d) for d in devices]

        return jsonify({
            'success': True,
            'devices': enriched
        }), 200

    except Exception as e:
        logger.error(f"Get devices error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/devices/<int:device_id>/heartbeats', methods=['GET'])
def get_device_heartbeats(device_id: int):
    """
    Get recent heartbeats for a specific device

    Query params:
        limit: Maximum number of heartbeats to return (default 100)

    Response JSON:
        {
            "success": true,
            "heartbeats": [...]
        }
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        heartbeats = db.get_device_heartbeats(device_id, limit)

        return jsonify({
            'success': True,
            'heartbeats': heartbeats
        }), 200

    except Exception as e:
        logger.error(f"Get heartbeats error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/devices/<int:device_id>', methods=['DELETE'])
def delete_device(device_id: int):
    """
    Delete a device and all its associated heartbeats

    Response JSON:
        {
            "success": true,
            "message": "Device deleted successfully"
        }
    """
    try:
        deleted = db.delete_device(device_id)

        if deleted:
            return jsonify({
                'success': True,
                'message': 'Device deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Device not found'
            }), 404

    except Exception as e:
        logger.error(f"Delete device error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


# Registration code management endpoints

@api_bp.route('/registration-codes', methods=['POST'])
def create_registration_code():
    """
    Create a new one-time registration code

    Request JSON:
        {
            "store_code": "FYSHWICK",
            "device_label": "Front Counter",
            "expires_hours": 24  // optional, default 24
        }

    Response JSON:
        {
            "success": true,
            "code": "ABC12345",
            "store_code": "FYSHWICK",
            "device_label": "Front Counter",
            "expires_at": "2025-11-21T12:00:00"
        }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'No JSON data provided'
            }), 400

        store_code = data.get('store_code', '').strip()
        device_label = data.get('device_label', '').strip()
        expires_hours = data.get('expires_hours', 24)

        if not store_code:
            return jsonify({
                'success': False,
                'error': 'store_code is required'
            }), 400

        if not device_label:
            return jsonify({
                'success': False,
                'error': 'device_label is required'
            }), 400

        # Create registration code
        code_data = db.create_registration_code(
            store_code=store_code,
            device_label=device_label,
            expires_hours=expires_hours
        )

        logger.info(f"Created registration code {code_data['code']} for {store_code}/{device_label}")

        return jsonify({
            'success': True,
            'code': code_data['code'],
            'store_code': code_data['store_code'],
            'device_label': code_data['device_label'],
            'expires_at': code_data['expires_at']
        }), 201

    except Exception as e:
        logger.error(f"Create registration code error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/registration-codes', methods=['GET'])
def get_registration_codes():
    """
    Get all registration codes (for admin view)

    Response JSON:
        {
            "success": true,
            "codes": [...]
        }
    """
    try:
        codes = db.get_all_registration_codes()

        return jsonify({
            'success': True,
            'codes': codes
        }), 200

    except Exception as e:
        logger.error(f"Get registration codes error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_bp.route('/registration-codes/<int:code_id>', methods=['DELETE'])
def delete_registration_code(code_id: int):
    """
    Delete a registration code

    Response JSON:
        {
            "success": true,
            "message": "Registration code deleted successfully"
        }
    """
    try:
        deleted = db.delete_registration_code(code_id)

        if deleted:
            return jsonify({
                'success': True,
                'message': 'Registration code deleted successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Registration code not found'
            }), 404

    except Exception as e:
        logger.error(f"Delete registration code error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
