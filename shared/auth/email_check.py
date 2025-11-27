"""
Shared email authorization functions.
"""


def is_email_allowed_by_domain(email: str, allowed_domains: list) -> bool:
    """
    Check if email is from an allowed domain.

    Args:
        email: Email address to check
        allowed_domains: List of allowed domain names (e.g., ['watsonblinds.com.au'])

    Returns:
        True if email domain is in allowed list
    """
    if not email or not allowed_domains:
        return False

    email = email.lower().strip()

    for domain in allowed_domains:
        if email.endswith(f'@{domain.lower()}'):
            return True

    return False


def is_email_allowed_by_list(email: str, allowed_emails: list) -> bool:
    """
    Check if email is in an allowed list.

    Args:
        email: Email address to check
        allowed_emails: List of allowed email addresses

    Returns:
        True if email is in allowed list
    """
    if not email or not allowed_emails:
        return False

    email = email.lower().strip()
    return email in [e.lower().strip() for e in allowed_emails]


def is_email_allowed(email: str, allowed_domains: list = None, admin_emails: list = None) -> bool:
    """
    Check if email is allowed based on domains and/or admin list.

    This is a convenience function that combines domain and list checks.
    Access is granted if email matches ANY of the criteria.

    Args:
        email: Email address to check
        allowed_domains: Optional list of allowed domains
        admin_emails: Optional list of admin emails

    Returns:
        True if email is allowed by domain OR is in admin list
    """
    if not email:
        return False

    # Check domain-based access
    if allowed_domains and is_email_allowed_by_domain(email, allowed_domains):
        return True

    # Check admin list access
    if admin_emails and is_email_allowed_by_list(email, admin_emails):
        return True

    return False


def is_admin_user(email: str, admin_emails: list) -> bool:
    """
    Check if email is an admin.

    Args:
        email: Email address to check
        admin_emails: List of admin email addresses

    Returns:
        True if email is in admin list
    """
    return is_email_allowed_by_list(email, admin_emails)
