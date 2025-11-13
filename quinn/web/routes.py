from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.db import db
from services.google_groups import groups_service
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@web_bp.route('/')
@require_auth
def index():
    """Display all external staff and pending requests"""
    status_filter = request.args.get('status', 'active')
    staff = db.get_all_staff(status=status_filter if status_filter != 'all' else None)
    pending_requests = db.get_pending_requests(status='pending')

    # Get all members from Google Group
    group_members = groups_service.get_all_members()

    # Find members in group but not in database
    staff_emails = {s['email'].lower() for s in staff}

    # Categorize other members
    company_staff = []
    unmanaged_external = []

    for member in group_members:
        if not member.get('email'):
            continue

        email = member['email'].lower()
        if email in staff_emails:
            continue  # Already in Quinn's database

        # Check if email is from company domain
        is_company = any(email.endswith(f'@{domain}') for domain in config.organization_domains)

        if is_company:
            company_staff.append(member)
        else:
            unmanaged_external.append(member)

    return render_template('index.html',
                         staff=staff,
                         status_filter=status_filter,
                         pending_requests=pending_requests,
                         company_staff=company_staff,
                         unmanaged_external=unmanaged_external)

@web_bp.route('/add', methods=['GET', 'POST'])
@require_auth
def add_staff():
    """Add new external staff member"""
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone', '')
        role = request.form.get('role', '')
        notes = request.form.get('notes', '')

        if not name or not email:
            return render_template('add.html', error='Name and email are required')

        added_by = session.get('user', {}).get('email', 'unknown')

        result = db.add_staff(name, email, phone, role, added_by, notes)

        if 'error' in result:
            return render_template('add.html', error=result['error'])

        # Add to Google Group
        groups_service.add_member(email)

        return redirect(url_for('web.index'))

    return render_template('add.html')

@web_bp.route('/edit/<int:staff_id>', methods=['GET', 'POST'])
@require_auth
def edit_staff(staff_id):
    """Edit existing staff member"""
    staff = db.get_staff_by_id(staff_id)

    if not staff:
        return redirect(url_for('web.index'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        role = request.form.get('role')
        status = request.form.get('status')
        notes = request.form.get('notes')

        # Check if status changed
        old_status = staff['status']

        result = db.update_staff(
            staff_id=staff_id,
            name=name,
            email=email,
            phone=phone,
            role=role,
            status=status,
            notes=notes
        )

        if 'error' in result:
            return render_template('edit.html', staff=staff, error=result['error'])

        # Update Google Group membership if status changed
        if status != old_status:
            if status == 'active':
                groups_service.add_member(email)
            else:
                groups_service.remove_member(email)

        return redirect(url_for('web.index'))

    return render_template('edit.html', staff=staff)

@web_bp.route('/delete/<int:staff_id>', methods=['POST'])
@require_auth
def delete_staff(staff_id):
    """Delete (deactivate) staff member"""
    staff = db.get_staff_by_id(staff_id)

    if staff:
        db.delete_staff(staff_id)
        groups_service.remove_member(staff['email'])

    return redirect(url_for('web.index'))


@web_bp.route('/approve-request/<int:request_id>', methods=['POST'])
@require_auth
def approve_request(request_id):
    """Approve a pending access request"""
    reviewed_by = session.get('user', {}).get('email', 'unknown')
    request_info = db.get_request_by_id(request_id)

    if request_info:
        result = db.approve_request(request_id, reviewed_by)

        if 'error' not in result:
            # Add to Google Group
            groups_service.add_member(request_info['email'])

    return redirect(url_for('web.index'))


@web_bp.route('/deny-request/<int:request_id>', methods=['POST'])
@require_auth
def deny_request(request_id):
    """Deny a pending access request"""
    reviewed_by = session.get('user', {}).get('email', 'unknown')
    notes = request.form.get('notes', '')

    db.deny_request(request_id, reviewed_by, notes)

    return redirect(url_for('web.index'))


@web_bp.route('/import-from-group/<path:email>', methods=['POST'])
@require_auth
def import_from_group(email):
    """Import an existing group member into Quinn's database"""
    added_by = session.get('user', {}).get('email', 'unknown')

    # Add to database - use email username as placeholder name
    name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()

    result = db.add_staff(
        name=name,
        email=email,
        phone='',
        role='',
        added_by=added_by,
        notes='Auto-imported from existing Google Group membership'
    )

    # No need to add to Google Group - they're already in it!

    return redirect(url_for('web.index'))


@web_bp.route('/bulk-import-from-group', methods=['POST'])
@require_auth
def bulk_import_from_group():
    """Import multiple existing group members into Quinn's database"""
    added_by = session.get('user', {}).get('email', 'unknown')
    emails = request.form.getlist('emails')

    imported_count = 0
    for email in emails:
        # Add to database - use email username as placeholder name
        name = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()

        result = db.add_staff(
            name=name,
            email=email,
            phone='',
            role='',
            added_by=added_by,
            notes='Auto-imported from existing Google Group membership'
        )

        if 'success' in result:
            imported_count += 1

    # No need to add to Google Group - they're already in it!

    return redirect(url_for('web.index'))


# Public routes (no authentication required)

@web_bp.route('/public/check', methods=['GET', 'POST'])
def public_check():
    """Public page to check if an email is approved"""
    result = None
    email = None

    if request.method == 'POST':
        email = request.form.get('email', '').strip()

        if email:
            approval = db.is_approved(email)
            result = {
                'email': email,
                'approved': approval.get('approved', False)
            }

    return render_template('public_check.html', result=result, email=email)


@web_bp.route('/public/request-access', methods=['GET', 'POST'])
def public_request():
    """Public page to request access"""
    success = False
    error = None
    email = None

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        reason = request.form.get('reason', '').strip()

        if not name or not email:
            error = 'Name and email are required'
        else:
            result = db.submit_request(name, email, phone, reason)

            if 'error' in result:
                if result.get('already_approved'):
                    error = 'This email is already approved. You should be able to access the system.'
                elif result.get('already_pending'):
                    error = 'A request for this email is already pending review.'
                else:
                    error = result['error']
            else:
                success = True

    return render_template('public_request.html', success=success, error=error, email=email)
