"""Health check endpoints for Mabel."""

import time

from flask import Blueprint, current_app, jsonify


health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Basic health check endpoint.

    Returns:
        JSON with status, name, version, and uptime
    """
    config = current_app.config['MABEL_CONFIG']
    start_time = current_app.config['START_TIME']
    uptime_seconds = time.time() - start_time

    return jsonify({
        'status': 'ok',
        'name': config.name,
        'version': config.version,
        'uptime_seconds': round(uptime_seconds, 2)
    }), 200


@health_bp.route('/health/deep', methods=['GET'])
def health_deep():
    """
    Deep health check that tests SMTP connection.

    Returns:
        JSON with status and SMTP connectivity details
    """
    config = current_app.config['MABEL_CONFIG']
    email_sender = current_app.config['EMAIL_SENDER']
    start_time = current_app.config['START_TIME']
    uptime_seconds = time.time() - start_time

    # Test SMTP connection
    smtp_test_start = time.time()
    smtp_ok = email_sender.test_connection()
    smtp_test_duration_ms = (time.time() - smtp_test_start) * 1000

    response = {
        'status': 'ok' if smtp_ok else 'degraded',
        'name': config.name,
        'version': config.version,
        'uptime_seconds': round(uptime_seconds, 2),
        'smtp_ok': smtp_ok,
        'details': {
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'smtp_use_tls': config.smtp_use_tls,
            'smtp_test_duration_ms': round(smtp_test_duration_ms, 2)
        }
    }

    status_code = 200 if smtp_ok else 503
    return jsonify(response), status_code
