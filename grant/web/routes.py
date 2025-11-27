"""Web routes for Grant's admin UI."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from services.auth import login_required
from services.permissions import permission_service

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
@login_required
def index():
    """Dashboard showing all permissions."""
    permissions = permission_service.get_all_permissions()
    bots = permission_service.get_bots()
    stats = permission_service.get_stats()

    return render_template(
        'index.html',
        permissions=permissions,
        bots=bots,
        stats=stats
    )


@web_bp.route('/users')
@login_required
def users():
    """List all users with their permissions."""
    all_permissions = permission_service.get_all_permissions()

    # Group permissions by user
    users_dict = {}
    for perm in all_permissions:
        email = perm['email']
        if email not in users_dict:
            users_dict[email] = []
        users_dict[email].append(perm)

    # Sort by email
    users_list = sorted(users_dict.items(), key=lambda x: x[0])

    return render_template('users.html', users=users_list)


@web_bp.route('/bots')
@login_required
def bots():
    """List all bots with their permissions."""
    all_bots = permission_service.get_bots()
    all_permissions = permission_service.get_all_permissions()

    # Group permissions by bot
    bots_dict = {bot['name']: [] for bot in all_bots}
    for perm in all_permissions:
        bot_name = perm['bot_name']
        if bot_name not in bots_dict:
            bots_dict[bot_name] = []
        bots_dict[bot_name].append(perm)

    return render_template('bots.html', bots=all_bots, permissions=bots_dict)


@web_bp.route('/audit')
@login_required
def audit():
    """Audit log of permission changes."""
    email_filter = request.args.get('email')
    bot_filter = request.args.get('bot')
    limit = request.args.get('limit', 100, type=int)

    audit_log = permission_service.get_audit_log(email_filter, bot_filter, limit)

    return render_template(
        'audit.html',
        audit=audit_log,
        email_filter=email_filter,
        bot_filter=bot_filter
    )


@web_bp.route('/grant', methods=['GET', 'POST'])
@login_required
def grant():
    """Grant permission form."""
    bots = permission_service.get_bots()

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        bot_name = request.form.get('bot', '').strip()
        role = request.form.get('role', 'user').strip()

        if not email:
            flash('Email is required', 'error')
        elif not bot_name:
            flash('Bot is required', 'error')
        else:
            try:
                permission_service.grant_permission(
                    email=email,
                    bot_name=bot_name,
                    role=role,
                    granted_by=current_user.email
                )
                flash(f'Granted {role} access to {email} for {bot_name}', 'success')
                return redirect(url_for('web.index'))
            except Exception as e:
                flash(f'Error: {e}', 'error')

    return render_template('grant.html', bots=bots)


@web_bp.route('/revoke', methods=['POST'])
@login_required
def revoke():
    """Revoke permission."""
    email = request.form.get('email', '').strip()
    bot_name = request.form.get('bot', '').strip()

    if not email or not bot_name:
        flash('Email and bot are required', 'error')
    else:
        revoked = permission_service.revoke_permission(
            email=email,
            bot_name=bot_name,
            revoked_by=current_user.email
        )
        if revoked:
            flash(f'Revoked access from {email} for {bot_name}', 'success')
        else:
            flash(f'No permission found for {email} on {bot_name}', 'warning')

    return redirect(request.referrer or url_for('web.index'))


@web_bp.route('/sync', methods=['POST'])
@login_required
def sync_bots():
    """Sync bot registry from Chester."""
    result = permission_service.sync_bots_from_chester()

    if result['success']:
        flash(f"Synced {result['synced']} bots from Chester", 'success')
    else:
        flash(f"Sync failed: {result['error']}", 'error')

    return redirect(request.referrer or url_for('web.index'))


@web_bp.route('/bots/<bot_name>/access-policy', methods=['POST'])
@login_required
def update_bot_access_policy(bot_name):
    """Update a bot's default access policy."""
    default_access = request.form.get('default_access', '').strip()

    if default_access not in ('domain', 'explicit'):
        flash('Invalid access policy', 'error')
    else:
        try:
            updated = permission_service.update_bot_access_policy(bot_name, default_access)
            if updated:
                policy_label = 'Domain (all staff)' if default_access == 'domain' else 'Explicit (invite only)'
                flash(f"Updated {bot_name} access policy to: {policy_label}", 'success')
            else:
                flash(f'Bot {bot_name} not found', 'error')
        except Exception as e:
            flash(f'Error: {e}', 'error')

    return redirect(request.referrer or url_for('web.bots'))
