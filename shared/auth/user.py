"""
Shared User class for Flask-Login authentication.
"""
from flask_login import UserMixin


class User(UserMixin):
    """
    User model for Flask-Login.

    Attributes:
        id: User ID (typically email)
        email: User's email address
        name: User's display name
        picture: Optional profile picture URL
        _admin_emails: List of admin emails for is_admin check
    """

    def __init__(self, email: str, name: str = None, picture: str = None, admin_emails: list = None):
        """
        Initialize a User.

        Args:
            email: User's email address (also used as ID)
            name: Display name (defaults to email if not provided)
            picture: Optional profile picture URL
            admin_emails: Optional list of admin emails for is_admin check
        """
        self.id = email
        self.email = email
        self.name = name or email
        self.picture = picture
        self._admin_emails = admin_emails or []
        self._is_admin_cached = None

    @property
    def is_admin(self) -> bool:
        """
        Check if user is an admin.

        Returns:
            True if user's email is in the admin_emails list
        """
        if self._is_admin_cached is None:
            if not self._admin_emails:
                self._is_admin_cached = False
            else:
                self._is_admin_cached = self.email.lower() in [e.lower() for e in self._admin_emails]
        return self._is_admin_cached

    @staticmethod
    def from_google_info(user_info: dict, admin_emails: list = None) -> 'User':
        """
        Create a User from Google OAuth user info.

        Args:
            user_info: Dict from Google OAuth with email, name, picture
            admin_emails: Optional list of admin emails

        Returns:
            User instance
        """
        return User(
            email=user_info.get('email', ''),
            name=user_info.get('name'),
            picture=user_info.get('picture'),
            admin_emails=admin_emails
        )

    def __repr__(self):
        return f"<User {self.email}>"
