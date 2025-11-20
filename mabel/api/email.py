"""Email sending API endpoints for Mabel."""

import logging
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, request
from pydantic import ValidationError

from services.email_models import EmailRequest
from services.email_sender import EmailSendError


logger = logging.getLogger(__name__)

email_bp = Blueprint('email', __name__)


def require_api_key(f):
    """
    Decorator to require API key authentication.

    Checks for X-Internal-Api-Key header and validates against config.
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = current_app.config['MABEL_CONFIG']
        api_key = request.headers.get('X-Internal-Api-Key')

        if not api_key or api_key != config.internal_api_key:
            return jsonify({'error': 'unauthorized'}), 401

        return f(*args, **kwargs)

    return decorated_function


@email_bp.route('/send-email', methods=['POST'])
@require_api_key
def send_email():
    """
    Send a single email.

    Expects JSON body matching EmailRequest schema.

    Returns:
        200: Email sent successfully
        400: Validation error
        401: Unauthorized
        502: Send failed (SMTP error)
    """
    # Get JSON body
    if not request.is_json:
        return jsonify({
            'error': 'validation_error',
            'details': 'Content-Type must be application/json'
        }), 400

    data = request.get_json()

    # Inject correlation ID from header into metadata if not present
    correlation_id = request.headers.get('X-Correlation-Id')
    if correlation_id:
        if 'metadata' not in data:
            data['metadata'] = {}
        if 'correlation_id' not in data['metadata']:
            data['metadata']['correlation_id'] = correlation_id

    # Validate request
    try:
        email_request = EmailRequest(**data)
    except ValidationError as e:
        logger.warning(f"Email validation failed: {e}")
        # Convert Pydantic errors to JSON-serializable format
        errors = []
        for error in e.errors():
            errors.append({
                'type': error.get('type'),
                'loc': error.get('loc'),
                'msg': error.get('msg'),
                'input': str(error.get('input')) if error.get('input') is not None else None
            })
        return jsonify({
            'error': 'validation_error',
            'details': errors
        }), 400

    # Send email
    email_sender = current_app.config['EMAIL_SENDER']

    try:
        message_id = email_sender.send(email_request)

        return jsonify({
            'status': 'sent',
            'message_id': message_id,
            'to': email_request.to,
            'subject': email_request.subject,
            'provider': 'smtp'
        }), 200

    except EmailSendError as e:
        logger.error(f"Email send failed: {e}")
        return jsonify({
            'error': 'send_failed',
            'details': 'Failed to send email via SMTP'  # Redacted error
        }), 502


@email_bp.route('/send-batch', methods=['POST'])
@require_api_key
def send_batch():
    """
    Send multiple emails in batch.

    Expects JSON body with 'emails' array, each matching EmailRequest schema.

    Returns:
        200: Batch processing complete (individual results included)
        400: Validation error
        401: Unauthorized
    """
    # Get JSON body
    if not request.is_json:
        return jsonify({
            'error': 'validation_error',
            'details': 'Content-Type must be application/json'
        }), 400

    data = request.get_json()

    # Validate batch structure
    if not isinstance(data, dict) or 'emails' not in data:
        return jsonify({
            'error': 'validation_error',
            'details': "Body must be JSON object with 'emails' array"
        }), 400

    emails_data = data['emails']
    if not isinstance(emails_data, list):
        return jsonify({
            'error': 'validation_error',
            'details': "'emails' must be an array"
        }), 400

    if len(emails_data) == 0:
        return jsonify({
            'error': 'validation_error',
            'details': "'emails' array cannot be empty"
        }), 400

    # Process each email
    results: List[Dict[str, Any]] = []
    email_sender = current_app.config['EMAIL_SENDER']
    correlation_id = request.headers.get('X-Correlation-Id', 'none')

    for idx, email_data in enumerate(emails_data):
        result: Dict[str, Any] = {'index': idx}

        # Inject correlation ID
        if 'metadata' not in email_data:
            email_data['metadata'] = {}
        if 'correlation_id' not in email_data['metadata']:
            email_data['metadata']['correlation_id'] = f"{correlation_id}-{idx}"

        # Validate
        try:
            email_request = EmailRequest(**email_data)
        except ValidationError as e:
            result['status'] = 'validation_error'
            # Convert Pydantic errors to JSON-serializable format
            errors = []
            for error in e.errors():
                errors.append({
                    'type': error.get('type'),
                    'loc': error.get('loc'),
                    'msg': error.get('msg')
                })
            result['error'] = errors
            results.append(result)
            continue

        # Send
        try:
            message_id = email_sender.send(email_request)
            result['status'] = 'sent'
            result['message_id'] = message_id
            result['to'] = email_request.to
            result['subject'] = email_request.subject
        except EmailSendError as e:
            result['status'] = 'send_failed'
            result['error'] = 'SMTP error (redacted)'
            logger.error(f"Batch email {idx} failed: {e}")

        results.append(result)

    # Count successes
    success_count = sum(1 for r in results if r.get('status') == 'sent')
    failure_count = len(results) - success_count

    return jsonify({
        'status': 'completed',
        'total': len(results),
        'success_count': success_count,
        'failure_count': failure_count,
        'results': results
    }), 200
