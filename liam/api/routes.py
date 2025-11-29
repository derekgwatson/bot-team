"""API routes for Liam."""
import logging
import threading
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request

from shared.auth.bot_api import api_key_required, api_or_session_auth
from config import config
from database.db import leads_db
from services.odata_client import ODataClientFactory
from services.leads_service import LeadsVerificationService
from services.analytics_service import AnalyticsService
from services.data_collection_service import DataCollectionService
from services.auth import get_current_user

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize services
odata_factory = ODataClientFactory(config)
leads_service = LeadsVerificationService(config, odata_factory, leads_db)
analytics_service = AnalyticsService(config, leads_db)
data_collection_service = DataCollectionService(config, odata_factory, leads_db)

# Track running background jobs
_running_backfill = {'thread': None, 'started_by': None, 'days': None}


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


# === Data Collection Endpoints ===

@api_bp.route('/data/collect', methods=['POST'])
@api_or_session_auth
def collect_data():
    """
    Collect daily lead counts for storage/analytics.

    This is called daily by Skye to populate the analytics database.

    Request Body (optional):
        date: Date to collect (YYYY-MM-DD), defaults to yesterday
        org: Specific org to collect (optional, defaults to all)

    Returns:
        JSON with collection results
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

        org_key = data.get('org')

        if org_key:
            # Collect for single org
            result = data_collection_service.collect_daily_data(
                org_key=org_key,
                date=date
            )
            return jsonify(result), 200
        else:
            # Collect for all orgs
            results = data_collection_service.collect_all_orgs(date=date)
            return jsonify(results), 200

    except Exception as e:
        logger.exception(f"Error in collect_data: {e}")
        return jsonify({'error': str(e)}), 500


def _run_backfill_background(days, skip_existing, started_by):
    """Run backfill in background thread."""
    global _running_backfill
    try:
        logger.info(f"Background backfill started by {started_by}: {days} days")
        results = data_collection_service.backfill_all_orgs(
            days=days,
            skip_existing=skip_existing
        )

        # Log summary
        total_collected = sum(
            len(org.get('collected', []))
            for org in results.get('orgs', {}).values()
        )
        total_errors = sum(
            len(org.get('errors', []))
            for org in results.get('orgs', {}).values()
        )
        logger.info(
            f"Background backfill completed by {started_by}: "
            f"{total_collected} days collected, {total_errors} errors"
        )

    except Exception as e:
        logger.exception(f"Background backfill failed: {e}")
    finally:
        _running_backfill['thread'] = None
        _running_backfill['started_by'] = None
        _running_backfill['days'] = None


@api_bp.route('/data/backfill', methods=['POST'])
@api_or_session_auth
def backfill_data():
    """
    Backfill historical lead data (non-blocking).

    Returns 202 immediately and runs backfill in background.

    Request Body:
        days: Number of days to backfill (default: 30)
        skip_existing: Skip dates with existing data (default: true)

    Returns:
        202 Accepted if started
        409 Conflict if already running
    """
    global _running_backfill

    # Check if backfill is already running
    if _running_backfill['thread'] is not None and _running_backfill['thread'].is_alive():
        return jsonify({
            'success': False,
            'error': 'A backfill is already running',
            'started_by': _running_backfill['started_by'],
            'days': _running_backfill['days']
        }), 409

    try:
        data = request.get_json() or {}
        days = data.get('days', 30)
        skip_existing = data.get('skip_existing', True)

        # Get current user for logging
        user = get_current_user()
        started_by = user.email if user else 'api'

        # Start background thread
        thread = threading.Thread(
            target=_run_backfill_background,
            args=(days, skip_existing, started_by),
            daemon=True
        )
        thread.start()

        _running_backfill['thread'] = thread
        _running_backfill['started_by'] = started_by
        _running_backfill['days'] = days

        logger.info(f"Started background backfill for {days} days by {started_by}")

        return jsonify({
            'success': True,
            'message': f'Backfill started for {days} days across {len(config.available_orgs)} orgs',
            'days': days,
            'orgs': list(config.available_orgs),
            'note': 'Check Analytics page for results when complete'
        }), 202

    except Exception as e:
        logger.exception(f"Error starting backfill: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/data/backfill/status', methods=['GET'])
@api_or_session_auth
def backfill_status():
    """Check if a backfill is currently running."""
    is_running = _running_backfill['thread'] is not None and _running_backfill['thread'].is_alive()
    return jsonify({
        'success': True,
        'running': is_running,
        'started_by': _running_backfill['started_by'] if is_running else None,
        'days': _running_backfill['days'] if is_running else None
    })


# === Analytics Endpoints ===

@api_bp.route('/analytics/trends', methods=['GET'])
@api_or_session_auth
def get_trends():
    """
    Get lead count trends over time.

    Query Parameters:
        org: Organization key (optional, defaults to all orgs)
        days: Number of days to analyze (default: 30)

    Returns:
        JSON with trend data including daily counts and statistics
    """
    try:
        org_key = request.args.get('org')
        days = request.args.get('days', 30, type=int)

        trends = analytics_service.get_lead_trends(
            org_key=org_key,
            days=days
        )

        return jsonify(trends), 200

    except Exception as e:
        logger.exception(f"Error in get_trends: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/compare', methods=['GET'])
@api_or_session_auth
def compare_periods():
    """
    Compare current period to previous period.

    Query Parameters:
        org: Organization key (required)
        period: 'week' or 'month' (default: week)

    Returns:
        JSON with current vs previous comparison
    """
    try:
        org_key = request.args.get('org')
        if not org_key:
            return jsonify({'error': 'org parameter is required'}), 400

        period = request.args.get('period', 'week')
        if period not in ['week', 'month']:
            return jsonify({'error': 'period must be "week" or "month"'}), 400

        comparison = analytics_service.get_period_comparison(
            org_key=org_key,
            period=period
        )

        return jsonify(comparison), 200

    except Exception as e:
        logger.exception(f"Error in compare_periods: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/day-of-week', methods=['GET'])
@api_or_session_auth
def analyze_day_of_week():
    """
    Analyze lead patterns by day of week.

    Query Parameters:
        org: Organization key (optional, defaults to all)
        weeks: Number of weeks to analyze (default: 4)

    Returns:
        JSON with average leads per day of week
    """
    try:
        org_key = request.args.get('org')
        weeks = request.args.get('weeks', 4, type=int)

        analysis = analytics_service.get_day_of_week_analysis(
            org_key=org_key,
            weeks=weeks
        )

        return jsonify(analysis), 200

    except Exception as e:
        logger.exception(f"Error in analyze_day_of_week: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/rankings', methods=['GET'])
@api_or_session_auth
def get_store_rankings():
    """
    Rank stores by lead performance.

    Query Parameters:
        days: Number of days to analyze (default: 7)

    Returns:
        JSON with stores ranked by total leads
    """
    try:
        days = request.args.get('days', 7, type=int)

        rankings = analytics_service.get_store_rankings(days=days)

        return jsonify({'rankings': rankings}), 200

    except Exception as e:
        logger.exception(f"Error in get_store_rankings: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analytics/campaign-impact/<int:event_id>', methods=['GET'])
@api_or_session_auth
def analyze_campaign_impact(event_id):
    """
    Analyze the impact of a marketing campaign.

    Path Parameters:
        event_id: Marketing event ID

    Query Parameters:
        baseline_days: Days before campaign to use as baseline (default: 7)

    Returns:
        JSON with campaign impact analysis
    """
    try:
        baseline_days = request.args.get('baseline_days', 7, type=int)

        impact = analytics_service.get_campaign_impact(
            event_id=event_id,
            baseline_days=baseline_days
        )

        if 'error' in impact:
            return jsonify(impact), 404

        return jsonify(impact), 200

    except Exception as e:
        logger.exception(f"Error in analyze_campaign_impact: {e}")
        return jsonify({'error': str(e)}), 500


# === Marketing Events Endpoints ===

@api_bp.route('/events', methods=['GET'])
@api_or_session_auth
def list_events():
    """
    List marketing events.

    Query Parameters:
        start_date: Filter events after this date (YYYY-MM-DD, optional)
        end_date: Filter events before this date (YYYY-MM-DD, optional)

    Returns:
        JSON array of marketing events
    """
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        events = leads_db.get_marketing_events(
            start_date=start_date,
            end_date=end_date
        )

        return jsonify({'events': events}), 200

    except Exception as e:
        logger.exception(f"Error in list_events: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/events', methods=['POST'])
@api_or_session_auth
def create_event():
    """
    Create a marketing event/campaign.

    Request Body:
        name: Event name (required)
        start_date: Start date YYYY-MM-DD (required)
        event_type: Type of event (default: 'campaign')
        description: Optional description
        end_date: Optional end date YYYY-MM-DD
        target_orgs: Optional array of org keys

    Returns:
        JSON with created event details
    """
    try:
        data = request.get_json()

        if not data or 'name' not in data or 'start_date' not in data:
            return jsonify({'error': 'name and start_date are required'}), 400

        # Get current user email if available
        user = get_current_user()
        created_by = user.email if user else None

        event_id = leads_db.create_marketing_event(
            name=data['name'],
            start_date=data['start_date'],
            event_type=data.get('event_type', 'campaign'),
            description=data.get('description', ''),
            end_date=data.get('end_date'),
            target_orgs=data.get('target_orgs'),
            created_by=created_by
        )

        return jsonify({
            'success': True,
            'event_id': event_id,
            'message': 'Event created successfully'
        }), 201

    except Exception as e:
        logger.exception(f"Error in create_event: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/events/<int:event_id>', methods=['DELETE'])
@api_or_session_auth
def delete_event(event_id):
    """
    Delete a marketing event.

    Path Parameters:
        event_id: Event ID to delete

    Returns:
        JSON with deletion result
    """
    try:
        deleted = leads_db.delete_marketing_event(event_id)

        if deleted:
            return jsonify({
                'success': True,
                'message': 'Event deleted successfully'
            }), 200
        else:
            return jsonify({'error': 'Event not found'}), 404

    except Exception as e:
        logger.exception(f"Error in delete_event: {e}")
        return jsonify({'error': str(e)}), 500
