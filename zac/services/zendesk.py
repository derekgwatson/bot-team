from zenpy import Zenpy
from zenpy.lib.api_objects import User
from config import config
import logging
from datetime import datetime, timedelta

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

        # Simple in-memory cache
        self._cache = {}
        self._cache_expiry = None
        self._cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

    def _fetch_all_users(self):
        """Fetch all users from Zendesk and cache them"""
        users = []
        logger.info("Fetching all users from Zendesk (this may take a while)...")

        for user in self.client.users():
            try:
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
            except Exception as user_error:
                logger.warning(f"Error processing user {getattr(user, 'id', 'unknown')}: {str(user_error)}")
                continue

        logger.info(f"Fetched {len(users)} users from Zendesk")
        return users

    def list_users(self, role=None, page=1, per_page=100):
        """
        List Zendesk users, optionally filtered by role
        Uses a 5-minute cache to avoid slow API calls

        Args:
            role: Optional role filter ('end-user', 'agent', 'admin')
            page: Page number (default: 1)
            per_page: Results per page (default: 100)

        Returns:
            List of user objects
        """
        try:
            # Check if cache is valid
            now = datetime.now()
            if self._cache_expiry is None or now > self._cache_expiry:
                logger.info("Cache expired or empty, fetching fresh data...")
                all_users = self._fetch_all_users()
                self._cache = {'all_users': all_users}
                self._cache_expiry = now + self._cache_ttl
            else:
                logger.info("Using cached user data")
                all_users = self._cache.get('all_users', [])

            # Filter by role if needed
            if role:
                users = [u for u in all_users if u['role'] == role]
            else:
                users = all_users

            # Manual pagination
            start = (page - 1) * per_page
            end = start + per_page
            page_users = users[start:end]

            # Calculate totals
            total = len(users)
            total_pages = (total + per_page - 1) // per_page if total > 0 else 1

            return {
                'users': page_users,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages,
                'cached': self._cache_expiry is not None,
                'cache_expires': str(self._cache_expiry) if self._cache_expiry else None
            }
        except Exception as e:
            logger.error(f"Error listing users: {str(e)}")
            raise

    def clear_cache(self):
        """Clear the user cache - call this after creating/updating/deleting users"""
        self._cache = {}
        self._cache_expiry = None
        logger.info("User cache cleared")

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

            # Clear cache so next list shows new user
            self.clear_cache()

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

            # Clear cache so changes are visible
            self.clear_cache()

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

            # Clear cache so changes are visible
            self.clear_cache()

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

            # Clear cache so changes are visible
            self.clear_cache()

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

            # Clear cache so deletion is visible
            self.clear_cache()

            return True
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise

# Initialize the service
zendesk_service = ZendeskService()
