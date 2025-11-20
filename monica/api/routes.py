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

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new device or retrieve existing device credentials

    Request JSON:
        {
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

        # Get or create store
        store_id = db.get_or_create_store(store_code)

        # Generate a secure agent token
        agent_token = secrets.token_urlsafe(32)

        # Get or create device
        device = db.get_or_create_device(store_id, device_label, agent_token)

        logger.info(
            f"Device registered: {store_code}/{device_label} "
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

        # Get optional network metrics
        latency_ms = data.get('latency_ms')
        download_mbps = data.get('download_mbps')

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
