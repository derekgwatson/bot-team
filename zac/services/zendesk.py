from zenpy import Zenpy
from zenpy.lib.api_objects import User
from config import config
import logging

logger = logging.getLogger(__name__)

class ZendeskService:
    """Service for managing Zendesk users via the Zendesk API"""

    def __init__(self):
        """Initialize the Zendesk client"""
        if not all([config.zendesk_subdomain, config.zendesk_email, config.zendesk_api_token]):
            raise ValueError("Zendesk credentials not configured. Please check your .env file.")

        self.client = Zenpy(
            subdomain=config.zendesk_subdomain,
            email=config.zendesk_email,
            token=config.zendesk_api_token
        )

    def list_users(self, role=None, page=1, per_page=50):
        """
        List Zendesk users, optionally filtered by role
        Only fetches enough users for the current page to avoid rate limits

        Args:
            role: Optional role filter ('end-user', 'agent', 'admin')
            page: Page number (default: 1)
            per_page: Results per page (default: 50)

        Returns:
            List of user objects
        """
        try:
            users = []
            count = 0
            max_needed = page * per_page + 1  # Fetch one extra to check if there are more pages

            logger.info(f"Fetching users for page {page} (max {max_needed} users)...")

            # Only fetch what we need for this page
            for user in self.client.users():
                try:
                    # Filter by role if specified
                    if role is not None and getattr(user, 'role', None) != role:
                        continue

                    users.append({
                        'id': getattr(user, 'id', None),
                        'name': getattr(user, 'name', 'Unknown'),
                        'email': getattr(user, 'email', 'No email'),
                        'role': getattr(user, 'role', 'end-user'),
                        'verified': getattr(user, 'verified', False),
                        'active': getattr(user, 'active', True),
                        'suspended': getattr(user, 'suspended', False),
                        'created_at': str(user.created_at) if hasattr(user, 'created_at') and user.created_at else None,
                        'last_login_at': str(user.last_login_at) if hasattr(user, 'last_login_at') and user.last_login_at else None,
                        'phone': getattr(user, 'phone', None),
                        'organization_id': getattr(user, 'organization_id', None)
                    })

                    # Stop once we have enough for this page plus one more
                    if len(users) >= max_needed:
                        logger.info(f"Fetched enough users ({len(users)}), stopping early")
                        break

                except Exception as user_error:
                    logger.warning(f"Error processing user {getattr(user, 'id', 'unknown')}: {str(user_error)}")
                    continue

            # Paginate
            start = (page - 1) * per_page
            end = start + per_page
            page_users = users[start:end]
            has_more = len(users) > end

            logger.info(f"Returning {len(page_users)} users for page {page}")

            return {
                'users': page_users,
                'total': f"{len(users)}+" if has_more else len(users),  # Approximate
                'page': page,
                'per_page': per_page,
                'total_pages': page + 1 if has_more else page,  # At least one more page
                'has_more': has_more
            }
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            raise

    def get_user(self, user_id):
        """
        Get a specific user by ID

        Args:
            user_id: Zendesk user ID

        Returns:
            User object or None if not found
        """
        try:
            user = self.client.users(id=user_id)
            return {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'role': user.role,
                'verified': user.verified,
                'active': user.active,
                'suspended': user.suspended,
                'created_at': str(user.created_at) if user.created_at else None,
                'last_login_at': str(user.last_login_at) if user.last_login_at else None,
                'phone': user.phone,
                'organization_id': user.organization_id,
                'locale': user.locale,
                'time_zone': user.time_zone,
                'notes': user.notes
            }
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {str(e)}")
            return None

    def search_users(self, query):
        """
        Search for users by name or email

        Args:
            query: Search query string

        Returns:
            List of matching user objects
        """
        try:
            users = []
            for user in self.client.search(type='user', name=query):
                users.append({
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'role': user.role,
                    'verified': user.verified,
                    'active': user.active,
                    'suspended': user.suspended
                })
            return users
        except Exception as e:
            logger.error(f"Error searching users: {str(e)}")
            raise

    def create_user(self, name, email, role='end-user', verified=False, **kwargs):
        """
        Create a new Zendesk user

        Args:
            name: User's full name
            email: User's email address
            role: User role ('end-user', 'agent', 'admin')
            verified: Whether the email is verified
            **kwargs: Additional user properties (phone, organization_id, etc.)

        Returns:
            Created user object
        """
        try:
            user = User(name=name, email=email, role=role, verified=verified)

            # Set additional properties
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            created_user = self.client.users.create(user)
            logger.info(f"Created user: {created_user.email} (ID: {created_user.id})")

            return {
                'id': created_user.id,
                'name': created_user.name,
                'email': created_user.email,
                'role': created_user.role,
                'verified': created_user.verified,
                'active': created_user.active
            }
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise

    def update_user(self, user_id, **kwargs):
        """
        Update a user's properties

        Args:
            user_id: Zendesk user ID
            **kwargs: Properties to update (name, email, role, phone, etc.)

        Returns:
            Updated user object
        """
        try:
            user = self.client.users(id=user_id)

            # Update properties
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)

            updated_user = self.client.users.update(user)
            logger.info(f"Updated user {user_id}")

            return {
                'id': updated_user.id,
                'name': updated_user.name,
                'email': updated_user.email,
                'role': updated_user.role,
                'verified': updated_user.verified,
                'active': updated_user.active,
                'suspended': updated_user.suspended
            }
        except Exception as e:
            logger.error(f"Error updating user {user_id}: {str(e)}")
            raise

    def suspend_user(self, user_id):
        """
        Suspend a user

        Args:
            user_id: Zendesk user ID

        Returns:
            Updated user object
        """
        try:
            user = self.client.users(id=user_id)
            user.suspended = True
            updated_user = self.client.users.update(user)
            logger.info(f"Suspended user {user_id}")

            return {
                'id': updated_user.id,
                'name': updated_user.name,
                'email': updated_user.email,
                'suspended': updated_user.suspended
            }
        except Exception as e:
            logger.error(f"Error suspending user {user_id}: {str(e)}")
            raise

    def unsuspend_user(self, user_id):
        """
        Unsuspend a user

        Args:
            user_id: Zendesk user ID

        Returns:
            Updated user object
        """
        try:
            user = self.client.users(id=user_id)
            user.suspended = False
            updated_user = self.client.users.update(user)
            logger.info(f"Unsuspended user {user_id}")

            return {
                'id': updated_user.id,
                'name': updated_user.name,
                'email': updated_user.email,
                'suspended': updated_user.suspended
            }
        except Exception as e:
            logger.error(f"Error unsuspending user {user_id}: {str(e)}")
            raise

    def delete_user(self, user_id):
        """
        Delete a user (permanently delete or deactivate depending on Zendesk plan)

        Args:
            user_id: Zendesk user ID

        Returns:
            Success boolean
        """
        try:
            self.client.users.delete(user_id)
            logger.info(f"Deleted user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise

# Initialize the service
zendesk_service = ZendeskService()
