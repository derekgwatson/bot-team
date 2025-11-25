from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, Comment
from config import config
import logging
import itertools

logger = logging.getLogger(__name__)

# Maximum results to fetch from Zendesk to prevent performance issues
MAX_RESULTS = 100

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

    def list_tickets(self, statuses=None, priority=None, group_id=None, page=1, per_page=25):
        """
        List Zendesk tickets, optionally filtered by status, priority, and group

        IMPORTANT: This method limits results to MAX_RESULTS total tickets to prevent
        performance issues with tens of thousands of tickets. Each page fetches fresh
        data from Zendesk, but we only ever show the first MAX_RESULTS tickets.

        Args:
            statuses: Optional status filter - can be a single status string or list of statuses
                     ('new', 'open', 'pending', 'hold', 'solved', 'closed')
            priority: Optional priority filter ('low', 'normal', 'high', 'urgent')
            group_id: Optional group ID filter (integer)
            page: Page number (default: 1)
            per_page: Results per page (default: 25)

        Returns:
            Dictionary with tickets list and pagination info
        """
        try:
            # Calculate how many tickets we need to fetch for this page
            # We fetch per_page + 1 to check if there are more results
            start_index = (page - 1) * per_page
            fetch_count = per_page + 1

            # Don't fetch beyond MAX_RESULTS
            if start_index >= MAX_RESULTS:
                logger.warning(f"Requested page {page} is beyond MAX_RESULTS limit ({MAX_RESULTS})")
                return {
                    'tickets': [],
                    'total': f"{MAX_RESULTS}+",
                    'page': page,
                    'per_page': per_page,
                    'total_pages': (MAX_RESULTS // per_page) + 1,
                    'has_more': False
                }

            # Adjust fetch count if we're near the limit
            if start_index + fetch_count > MAX_RESULTS:
                fetch_count = MAX_RESULTS - start_index + 1

            logger.info(f"Fetching tickets for page {page} (statuses={statuses}, priority={priority}, group_id={group_id}), "
                       f"indices {start_index} to {start_index + fetch_count - 1}...")

            # Try using Zenpy's search with status as a parameter (ChatGPT suggestion)
            # This should handle multi-status filtering server-side

            # Convert statuses to list if needed
            status_list = None
            if statuses:
                if isinstance(statuses, str):
                    status_list = [statuses]
                else:
                    status_list = statuses

            # Build search parameters
            search_params = {'type': 'ticket'}

            if status_list:
                search_params['status'] = status_list
            if priority:
                search_params['priority'] = priority
            if group_id:
                search_params['group'] = group_id

            logger.info(f"Search with params: {search_params}")

            # Use search if we have any filters, otherwise get all tickets
            if status_list or priority or group_id:
                search_results = self.client.search(**search_params)
            else:
                search_results = self.client.tickets()

            # Use itertools.islice to efficiently skip to our page and limit results
            # Server-side filtering should handle status/priority/group
            tickets = []
            skipped_count = 0
            iteration_count = 0

            # Iterate through results (already filtered by Zendesk)
            for ticket in itertools.islice(search_results, start_index, start_index + fetch_count):
                iteration_count += 1
                try:
                    tickets.append({
                        'id': getattr(ticket, 'id', None),
                        'subject': getattr(ticket, 'subject', 'No subject'),
                        'status': getattr(ticket, 'status', 'unknown'),
                        'priority': getattr(ticket, 'priority', None),
                        'type': getattr(ticket, 'type', None),
                        'requester_id': getattr(ticket, 'requester_id', None),
                        'assignee_id': getattr(ticket, 'assignee_id', None),
                        'group_id': getattr(ticket, 'group_id', None),
                        'organization_id': getattr(ticket, 'organization_id', None),
                        'created_at': str(ticket.created_at) if hasattr(ticket, 'created_at') and ticket.created_at else None,
                        'updated_at': str(ticket.updated_at) if hasattr(ticket, 'updated_at') and ticket.updated_at else None,
                        'tags': getattr(ticket, 'tags', []),
                        'has_incidents': getattr(ticket, 'has_incidents', False)
                    })
                except Exception as ticket_error:
                    skipped_count += 1
                    logger.warning(f"SKIPPED ticket {getattr(ticket, 'id', 'unknown')} - Error: {str(ticket_error)}")
                    continue

            logger.info(f"Iterated {iteration_count} times, collected {len(tickets)} tickets")

            if skipped_count > 0:
                logger.warning(f"⚠️ Skipped {skipped_count} tickets due to errors")

            # Check if there are more results (we fetched per_page + 1)
            has_more = len(tickets) > per_page
            if has_more:
                # Remove the extra ticket we fetched for checking
                tickets = tickets[:per_page]

            # Check if we hit the MAX_RESULTS limit
            hit_max_limit = iteration_count >= MAX_RESULTS

            logger.info(f"Returning {len(tickets)} tickets for page {page}")

            # Calculate total pages based on whether we have more results
            # If we hit max limit, we know we can have up to MAX_RESULTS // per_page pages
            # Otherwise, we show page + 1 if has_more, or just page if not
            if hit_max_limit:
                total_pages = MAX_RESULTS // per_page
            elif has_more:
                total_pages = page + 1  # We know there's at least one more page
            else:
                total_pages = page  # This is the last page

            result = {
                'tickets': tickets,
                'total': f"{MAX_RESULTS}+" if hit_max_limit else (f"{len(tickets) * page}+" if has_more else len(tickets) + (page - 1) * per_page),
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'has_more': has_more and not hit_max_limit
            }

            return result
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

    def search_tickets(self, query, limit=MAX_RESULTS):
        """
        Search for tickets by subject or content

        IMPORTANT: Limited to MAX_RESULTS to prevent performance issues

        Args:
            query: Search query string
            limit: Maximum number of results to return (default: MAX_RESULTS)

        Returns:
            List of matching ticket objects (limited to 'limit' results)
        """
        try:
            tickets = []
            # Use itertools.islice to limit results without loading everything
            for ticket in itertools.islice(self.client.search(type='ticket', query=query), limit):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })

            if len(tickets) == limit:
                logger.warning(f"Search returned {limit} results (limit reached). There may be more results.")

            return tickets
        except Exception as e:
            logger.error(f"Error searching tickets: {str(e)}")
            raise

    def get_user_tickets(self, user_id, limit=MAX_RESULTS):
        """
        Get tickets requested by a specific user

        IMPORTANT: Limited to MAX_RESULTS to prevent performance issues

        Args:
            user_id: Zendesk user ID
            limit: Maximum number of results to return (default: MAX_RESULTS)

        Returns:
            List of ticket objects (limited to 'limit' results)
        """
        try:
            tickets = []
            # Use itertools.islice to limit results
            for ticket in itertools.islice(self.client.users.requests(user_id), limit):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })

            if len(tickets) == limit:
                logger.warning(f"User {user_id} has {limit}+ tickets (limit reached)")

            return tickets
        except Exception as e:
            logger.error(f"Error getting tickets for user {user_id}: {str(e)}")
            raise

    def get_organization_tickets(self, organization_id, limit=MAX_RESULTS):
        """
        Get tickets for a specific organization

        IMPORTANT: Limited to MAX_RESULTS to prevent performance issues

        Args:
            organization_id: Zendesk organization ID
            limit: Maximum number of results to return (default: MAX_RESULTS)

        Returns:
            List of ticket objects (limited to 'limit' results)
        """
        try:
            tickets = []
            # Use itertools.islice to limit results
            for ticket in itertools.islice(self.client.organizations.tickets(organization_id), limit):
                tickets.append({
                    'id': ticket.id,
                    'subject': ticket.subject,
                    'status': ticket.status,
                    'priority': ticket.priority,
                    'requester_id': ticket.requester_id,
                    'created_at': str(ticket.created_at) if ticket.created_at else None,
                    'updated_at': str(ticket.updated_at) if ticket.updated_at else None
                })

            if len(tickets) == limit:
                logger.warning(f"Organization {organization_id} has {limit}+ tickets (limit reached)")

            return tickets
        except Exception as e:
            logger.error(f"Error getting tickets for organization {organization_id}: {str(e)}")
            raise

    def list_groups(self):
        """
        Get all Zendesk groups for filtering

        Returns:
            List of group objects with id and name
        """
        try:
            groups = []
            for group in self.client.groups():
                groups.append({
                    'id': group.id,
                    'name': group.name
                })

            # Sort by name for easier selection in UI
            groups.sort(key=lambda g: g['name'].lower())

            logger.info(f"Fetched {len(groups)} groups")
            return groups
        except Exception as e:
            logger.error(f"Error listing groups: {str(e)}")
            raise

    def create_ticket(self, subject, description, priority='normal', ticket_type='task', requester_id=None, group_id=None, tags=None):
        """
        Create a new Zendesk ticket

        Args:
            subject: Ticket subject line (required)
            description: Ticket description/body (required)
            priority: Ticket priority ('low', 'normal', 'high', 'urgent') - default: 'normal'
            ticket_type: Ticket type ('question', 'incident', 'problem', 'task') - default: 'task'
            requester_id: Zendesk user ID of the requester (optional)
            group_id: Zendesk group ID to assign the ticket to (optional)
            tags: List of tags to add to the ticket (optional)

        Returns:
            Dictionary with created ticket details including ticket ID and URL
        """
        try:
            # Create ticket object
            ticket = Ticket(
                subject=subject,
                description=description,
                priority=priority,
                type=ticket_type
            )

            # Add optional fields if provided
            if requester_id:
                ticket.requester_id = requester_id

            if group_id:
                ticket.group_id = group_id

            if tags:
                ticket.tags = tags if isinstance(tags, list) else [tags]

            # Create the ticket
            # Zenpy returns a TicketAudit object, the ticket is in .ticket
            result = self.client.tickets.create(ticket)
            created_ticket = result.ticket

            logger.info(f"Created ticket #{created_ticket.id}: {subject}")

            # Return ticket details
            return {
                'id': created_ticket.id,
                'subject': created_ticket.subject,
                'description': created_ticket.description,
                'status': created_ticket.status,
                'priority': created_ticket.priority,
                'type': created_ticket.type,
                'requester_id': created_ticket.requester_id,
                'group_id': created_ticket.group_id,
                'created_at': str(created_ticket.created_at) if created_ticket.created_at else None,
                'url': f"https://{config.zendesk_subdomain}.zendesk.com/agent/tickets/{created_ticket.id}",
                'tags': created_ticket.tags if hasattr(created_ticket, 'tags') else []
            }
        except Exception as e:
            logger.error(f"Error creating ticket: {str(e)}")
            raise

# Initialize the service
zendesk_ticket_service = ZendeskTicketService()
