from flask import Blueprint, jsonify, request
from services.auth import api_key_required
from services.zendesk import zendesk_ticket_service
import logging

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

@api_bp.route('/tickets', methods=['GET'])
@api_key_required
def list_tickets():
    """
    List all Zendesk tickets with optional filtering

    Query Parameters:
        status: Filter by status - can be specified multiple times for OR logic
                (new, open, pending, hold, solved, closed)
                Example: ?status=new&status=open&status=pending
        priority: Filter by priority (low, normal, high, urgent)
        group_id: Filter by group ID (integer)
        page: Page number (default: 1)
        per_page: Results per page (default: 25)

    Returns:
        JSON object with tickets list and pagination info
    """
    try:
        statuses = request.args.getlist('status')  # Get multiple status values
        priority = request.args.get('priority')
        group_id = request.args.get('group_id', type=int)
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))

        result = zendesk_ticket_service.list_tickets(
            statuses=statuses if statuses else None,
            priority=priority,
            group_id=group_id,
            page=page,
            per_page=per_page
        )
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error listing tickets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/groups', methods=['GET'])
@api_key_required
def list_groups():
    """
    Get all Zendesk groups for filtering

    Returns:
        JSON array of groups with id and name
    """
    try:
        groups = zendesk_ticket_service.list_groups()
        return jsonify({'groups': groups}), 200

    except Exception as e:
        logger.error(f"Error listing groups: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tickets/<int:ticket_id>', methods=['GET'])
@api_key_required
def get_ticket(ticket_id):
    """
    Get a specific ticket by ID with full details

    Args:
        ticket_id: Zendesk ticket ID

    Returns:
        JSON object with ticket details
    """
    try:
        ticket = zendesk_ticket_service.get_ticket(ticket_id)
        if ticket:
            return jsonify(ticket), 200
        else:
            return jsonify({'error': 'Ticket not found'}), 404

    except Exception as e:
        logger.error(f"Error getting ticket {ticket_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tickets/<int:ticket_id>/comments', methods=['GET'])
@api_key_required
def get_ticket_comments(ticket_id):
    """
    Get all comments for a specific ticket

    Args:
        ticket_id: Zendesk ticket ID

    Returns:
        JSON array of ticket comments
    """
    try:
        comments = zendesk_ticket_service.get_ticket_comments(ticket_id)
        return jsonify({'comments': comments}), 200

    except Exception as e:
        logger.error(f"Error getting comments for ticket {ticket_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/tickets/search', methods=['GET'])
@api_key_required
def search_tickets():
    """
    Search for tickets by subject or content

    Query Parameters:
        q: Search query string

    Returns:
        JSON array of matching tickets
    """
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'error': 'Search query required'}), 400

        tickets = zendesk_ticket_service.search_tickets(query)
        return jsonify({'tickets': tickets}), 200

    except Exception as e:
        logger.error(f"Error searching tickets: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/users/<int:user_id>/tickets', methods=['GET'])
@api_key_required
def get_user_tickets(user_id):
    """
    Get all tickets requested by a specific user

    Args:
        user_id: Zendesk user ID

    Returns:
        JSON array of tickets
    """
    try:
        tickets = zendesk_ticket_service.get_user_tickets(user_id)
        return jsonify({'tickets': tickets}), 200

    except Exception as e:
        logger.error(f"Error getting tickets for user {user_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/organizations/<int:organization_id>/tickets', methods=['GET'])
@api_key_required
def get_organization_tickets(organization_id):
    """
    Get all tickets for a specific organization

    Args:
        organization_id: Zendesk organization ID

    Returns:
        JSON array of tickets
    """
    try:
        tickets = zendesk_ticket_service.get_organization_tickets(organization_id)
        return jsonify({'tickets': tickets}), 200

    except Exception as e:
        logger.error(f"Error getting tickets for organization {organization_id}: {str(e)}")
        return jsonify({'error': str(e)}), 500
