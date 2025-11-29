"""API routes for Liam."""
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request

from shared.auth.bot_api import api_key_required, api_or_session_auth
from config import config
from database.db import leads_db
from services.odata_client import ODataClientFactory
from services.leads_service import LeadsVerificationService

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize services
odata_factory = ODataClientFactory(config)
leads_service = LeadsVerificationService(config, odata_factory, leads_db)


@api_bp.route('/leads/verify', methods=['POST'])
@api_or_session_auth
def verify_leads():
    """
    Run leads verification for all configured organizations.

    This is the main endpoint called by Skye's scheduled job.

    Request Body (optional):
        date: Date to verify (YYYY-MM-DD), defaults to yesterday
        create_tickets: Whether to create Zendesk tickets (default: true)
        org: Specific org to verify (optional, defaults to all)

    Returns:
        JSON with verification results for each org
    """
    try:
        data = request.get_json() or {}

        # Parse date parameter
        date_str = data.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                date = date.replace(tzinfo=timezone.utc)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        else:
            date = None  # Will default to yesterday

        create_tickets = data.get('create_tickets', True)
        org_key = data.get('org')

        if org_key:
            # Verify single org
            result = leads_service.verify_org(
                org_key=org_key,
                date=date,
                create_ticket=create_tickets
            )
            return jsonify(result), 200
        else:
            # Verify all orgs
            results = leads_service.verify_all(
                date=date,
                create_tickets=create_tickets
            )
            return jsonify(results), 200

    except Exception as e:
        logger.exception(f"Error in verify_leads: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/leads/history', methods=['GET'])
@api_or_session_auth
def get_history():
    """
    Get verification history.

    Query Parameters:
        org: Filter by organization (optional)
        limit: Maximum records to return (default: 50)

    Returns:
        JSON array of verification records
    """
    try:
        org_key = request.args.get('org')
        limit = request.args.get('limit', 50, type=int)

        history = leads_service.get_verification_history(
            org_key=org_key,
            limit=limit
        )

        return jsonify({'history': history}), 200

    except Exception as e:
        logger.exception(f"Error in get_history: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/leads/stats', methods=['GET'])
@api_or_session_auth
def get_stats():
    """
    Get verification statistics.

    Returns:
        JSON with stats by org and overall
    """
    try:
        stats = leads_service.get_stats()
        return jsonify(stats), 200

    except Exception as e:
        logger.exception(f"Error in get_stats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/orgs', methods=['GET'])
@api_key_required
def list_orgs():
    """
    List configured organizations.

    Returns:
        JSON with configured and missing credential orgs
    """
    try:
        configured = []
        for org_key in config.available_orgs:
            org_config = config.get_org_config(org_key)
            configured.append({
                'key': org_key,
                'code': org_config['code'],
                'display_name': org_config['display_name'],
                'is_primary': org_config.get('is_primary', False)
            })

        missing = []
        for org_key, info in config.missing_credentials.items():
            missing.append({
                'key': org_key,
                'code': info['code'],
                'display_name': info['display_name'],
                'missing_vars': info['missing']
            })

        return jsonify({
            'configured': configured,
            'missing_credentials': missing
        }), 200

    except Exception as e:
        logger.exception(f"Error in list_orgs: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/test-connections', methods=['POST'])
@api_or_session_auth
def test_connections():
    """
    Test OData connections for all configured organizations.

    Returns:
        JSON with connection test results per org
    """
    try:
        results = leads_service.test_connections()
        return jsonify({'results': results}), 200

    except Exception as e:
        logger.exception(f"Error in test_connections: {e}")
        return jsonify({'error': str(e)}), 500
