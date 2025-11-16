from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, Comment
from config import config
import logging

logger = logging.getLogger(__name__)

class ZendeskTicketService:
    """Service for managing Zendesk tickets via the Zendesk API"""

    def __init__(self):
        """Initialize the Zendesk client"""
        if not all([config.zendesk_subdomain, config.zendesk_email, config.zendesk_api_token]):
            raise ValueError("Zendesk credentials not configured. Please check your .env file.")

        self.client = Zenpy(
            subdomain=config.zendesk_subdomain,
            email=config.zendesk_email,
            token=config.zendesk_api_token
        )

    def list_tickets(self, status=None, priority=None, page=1, per_page=25):
        """
        List Zendesk tickets, optionally filtered by status and priority

        Args:
            status: Optional status filter ('new', 'open', 'pending', 'hold', 'solved', 'closed')
            priority: Optional priority filter ('low', 'normal', 'high', 'urgent')
            page: Page number (default: 1)
            per_page: Results per page (default: 25)

        Returns:
            Dictionary with tickets list and pagination info
        """
        try:
            tickets = []
            skipped_count = 0
            max_needed = page * per_page + 1  # Fetch one extra to check if there are more pages

            logger.info(f"Fetching tickets for page {page} (status={status}, priority={priority})...")

            # Use search API with filters for server-side filtering
            search_params = {'type': 'ticket'}
            if status:
                search_params['status'] = status
            if priority:
                search_params['priority'] = priority

            if status or priority:
                search_results = self.client.search(**search_params)
            else:
                # No filter - use regular ticket list
                search_results = self.client.tickets()

            # Only fetch what we need for this page
            for ticket in search_results:
                try:
                    tickets.append({
                        'id': getattr(ticket, 'id', None),
                        'subject': getattr(ticket, 'subject', 'No subject'),
                        'status': getattr(ticket, 'status', 'unknown'),
                        'priority': getattr(ticket, 'priority', None),
                        'type': getattr(ticket, 'type', None),
                        'requester_id': getattr(ticket, 'requester_id', None),
                        'assignee_id': getattr(ticket, 'assignee_id', None),
                        'organization_id': getattr(ticket, 'organization_id', None),
                        'created_at': str(ticket.created_at) if hasattr(ticket, 'created_at') and ticket.created_at else None,
                        'updated_at': str(ticket.updated_at) if hasattr(ticket, 'updated_at') and ticket.updated_at else None,
                        'tags': getattr(ticket, 'tags', []),
                        'has_incidents': getattr(ticket, 'has_incidents', False)
                    })

                    # Stop once we have enough for this page plus one more
                    if len(tickets) >= max_needed:
                        logger.info(f"Fetched enough tickets ({len(tickets)}), stopping early")
                        break

                except Exception as ticket_error:
                    skipped_count += 1
                    logger.warning(f"SKIPPED ticket {getattr(ticket, 'id', 'unknown')} - Error: {str(ticket_error)}")
                    continue

            if skipped_count > 0:
                logger.warning(f"⚠️ Skipped {skipped_count} tickets due to errors")

            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            page_tickets = tickets[start:end]
            has_more = len(tickets) > end

            logger.info(f"Returning {len(page_tickets)} tickets for page {page}")

            return {
                'tickets': page_tickets,
                'total': f"{len(tickets)}+" if has_more else len(tickets),
                'page': page,
                'per_page': per_page,
                'total_pages': page + 1 if has_more else page,
                'has_more': has_more
            }
        except Exception as e:
            logger.error(f"Error listing tickets: {str(e)}")
            raise

    def get_ticket(self, ticket_id):
        """
        Get a specific ticket by ID with full details

        Args:
            ticket_id: Zendesk ticket ID

        Returns:
            Ticket object with full details or None if not found
        """
        try:
            ticket = self.client.tickets(id=ticket_id)
            return {
                'id': ticket.id,
                'subject': ticket.subject,
                'description': ticket.description,
                'status': ticket.status,
                'priority': ticket.priority,
                'type': ticket.type,
                'requester_id': ticket.requester_id,
                'submitter_id': ticket.submitter_id,
                'assignee_id': ticket.assignee_id,
                'organization_id': ticket.organization_id,
                'group_id': ticket.group_id,
                'created_at': str(ticket.created_at) if ticket.created_at else None,
                'updated_at': str(ticket.updated_at) if ticket.updated_at else None,
                'due_at': str(ticket.due_at) if hasattr(ticket, 'due_at') and ticket.due_at else None,
                'tags': ticket.tags if hasattr(ticket, 'tags') else [],
                'via': ticket.via.to_dict() if hasattr(ticket, 'via') and ticket.via else None,
                'has_incidents': ticket.has_incidents if hasattr(ticket, 'has_incidents') else False,
                'is_public': ticket.is_public if hasattr(ticket, 'is_public') else True,
                'brand_id': ticket.brand_id if hasattr(ticket, 'brand_id') else None,
                'satisfaction_rating': ticket.satisfaction_rating.to_dict() if hasattr(ticket, 'satisfaction_rating') and ticket.satisfaction_rating else None
            }
        except Exception as e:
            logger.error(f"Error getting ticket {ticket_id}: {str(e)}")
            return None

    def get_ticket_comments(self, ticket_id):
        """
        Get all comments for a ticket

        Args:
            ticket_id: Zendesk ticket ID

        Returns:
            List of comment objects
        """
        try:
            comments = []
            for comment in self.client.tickets.comments(ticket=ticket_id):
                comments.append({
                    'id': comment.id,
                    'type': comment.type if hasattr(comment, 'type') else 'Comment',
                    'author_id': comment.author_id,
                    'body': comment.body if hasattr(comment, 'body') else comment.html_body,
                    'html_body': comment.html_body if hasattr(comment, 'html_body') else None,
                    'plain_body': comment.plain_body if hasattr(comment, 'plain_body') else None,
                    'public': comment.public,
                    'created_at': str(comment.created_at) if comment.created_at else None,
                    'attachments': [
                        {
                            'id': att.id,
                            'file_name': att.file_name,
                            'content_url': att.content_url,
                            'content_type': att.content_type,
                            'size': att.size
                        } for att in comment.attachments
                    ] if hasattr(comment, 'attachments') and comment.attachments else []
                })
            return comments
        except Exception as e:
            logger.error(f"Error getting comments for ticket {ticket_id}: {str(e)}")
            raise

    def search_tickets(self, query):
        """
        Search for tickets by subject or content

        Args:
            query: Search query string

        Returns:
            List of matching ticket objects
        """
        try:
            tickets = []
            for ticket in self.client.search(type='ticket', query=query):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })
            return tickets
        except Exception as e:
            logger.error(f"Error searching tickets: {str(e)}")
            raise

    def get_user_tickets(self, user_id):
        """
        Get all tickets requested by a specific user

        Args:
            user_id: Zendesk user ID

        Returns:
            List of ticket objects
        """
        try:
            tickets = []
            for ticket in self.client.users.requests(user_id):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })
            return tickets
        except Exception as e:
            logger.error(f"Error getting tickets for user {user_id}: {str(e)}")
            raise

    def get_organization_tickets(self, organization_id):
        """
        Get all tickets for a specific organization

        Args:
            organization_id: Zendesk organization ID

        Returns:
            List of ticket objects
        """
        try:
            tickets = []
            for ticket in self.client.organizations.tickets(organization_id):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'requester_id': ticket.requester_id,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })
            return tickets
        except Exception as e:
            logger.error(f"Error getting tickets for organization {organization_id}: {str(e)}")
            raise

# Initialize the service
zendesk_ticket_service = ZendeskTicketService()
