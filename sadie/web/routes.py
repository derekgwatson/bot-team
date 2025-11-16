from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.zendesk import zendesk_ticket_service
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')

@web_bp.route('/')
@login_required
def index():
    """Main dashboard - list all Zendesk tickets"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    priority_filter = request.args.get('priority')
    search_query = request.args.get('q')

    try:
        if search_query:
            # Search mode
            tickets = zendesk_ticket_service.search_tickets(search_query)
            result = {
                'tickets': tickets,
                'total': len(tickets),
                'page': 1,
                'per_page': len(tickets),
                'total_pages': 1,
                'has_more': False
            }
        else:
            # List mode with pagination
            result = zendesk_ticket_service.list_tickets(
                status=status_filter,
                priority=priority_filter,
                page=page,
                per_page=25
            )

        return render_template('index.html',
                             tickets=result['tickets'],
                             page=result['page'],
                             total_pages=result['total_pages'],
                             total=result['total'],
                             has_more=result.get('has_more', False),
                             status_filter=status_filter,
                             priority_filter=priority_filter,
                             search_query=search_query,
                             user=current_user)

    except Exception as e:
        return render_template('index.html',
                             error=str(e),
                             tickets=[],
                             page=1,
                             total_pages=1,
                             total=0,
                             has_more=False,
                             user=current_user)

@web_bp.route('/ticket/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    """View detailed information about a specific ticket"""
    try:
        ticket = zendesk_ticket_service.get_ticket(ticket_id)
        if not ticket:
            flash('Ticket not found', 'error')
            return redirect(url_for('web.index'))

        # Get comments for the ticket
        comments = zendesk_ticket_service.get_ticket_comments(ticket_id)

        return render_template('ticket_detail.html',
                             ticket=ticket,
                             comments=comments,
                             current_user=current_user)

    except Exception as e:
        flash(f'Error loading ticket: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/user/<int:user_id>/tickets')
@login_required
def user_tickets(user_id):
    """View all tickets for a specific user"""
    try:
        tickets = zendesk_ticket_service.get_user_tickets(user_id)
        return render_template('user_tickets.html',
                             tickets=tickets,
                             user_id=user_id,
                             current_user=current_user)

    except Exception as e:
        flash(f'Error loading user tickets: {str(e)}', 'error')
        return redirect(url_for('web.index'))

@web_bp.route('/organization/<int:organization_id>/tickets')
@login_required
def organization_tickets(organization_id):
    """View all tickets for a specific organization"""
    try:
        tickets = zendesk_ticket_service.get_organization_tickets(organization_id)
        return render_template('organization_tickets.html',
                             tickets=tickets,
                             organization_id=organization_id,
                             current_user=current_user)

    except Exception as e:
        flash(f'Error loading organization tickets: {str(e)}', 'error')
        return redirect(url_for('web.index'))
