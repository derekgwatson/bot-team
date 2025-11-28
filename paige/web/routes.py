"""Web routes for Paige - Dashboard and user management UI."""
from flask import Blueprint, render_template, flash, redirect, url_for, request
from services.auth import login_required
from services.dokuwiki_service import DokuWikiService
from config import config
import logging

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)

# Initialize the DokuWiki service
wiki_service = DokuWikiService(
    dokuwiki_path=config.dokuwiki_path,
    default_groups=config.default_groups
)


@web_bp.route('/')
@login_required
def index():
    """Dashboard showing wiki users and service status."""
    users = wiki_service.get_all_users()
    health = wiki_service.get_health_status()

    return render_template(
        'index.html',
        config=config,
        users=users,
        health=health
    )


@web_bp.route('/users/add', methods=['POST'])
@login_required
def add_user():
    """Add a new wiki user from the web UI."""
    login = request.form.get('login', '').strip().lower()
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()

    if not login or not name or not email:
        flash('All fields are required', 'error')
        return redirect(url_for('web.index'))

    result = wiki_service.add_user(login=login, name=name, email=email)

    if result['success']:
        flash(f'User {login} created successfully', 'success')
        logger.info(f"Web UI: Created wiki user {login}")
    else:
        flash(f"Failed to create user: {result.get('error')}", 'error')

    return redirect(url_for('web.index'))


@web_bp.route('/users/<login>/delete', methods=['POST'])
@login_required
def delete_user(login: str):
    """Delete a wiki user from the web UI."""
    result = wiki_service.remove_user(login)

    if result['success']:
        flash(f'User {login} deleted successfully', 'success')
        logger.info(f"Web UI: Deleted wiki user {login}")
    else:
        flash(f"Failed to delete user: {result.get('error')}", 'error')

    return redirect(url_for('web.index'))
