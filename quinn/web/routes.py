from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from database.db import db
from services.google_groups import groups_service

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
    """Display all external staff"""
    status_filter = request.args.get('status', 'active')
    staff = db.get_all_staff(status=status_filter if status_filter != 'all' else None)

    return render_template('index.html', staff=staff, status_filter=status_filter)

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
