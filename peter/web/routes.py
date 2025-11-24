from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user
from database.db import staff_db
from services.auth import login_required

web_bp = Blueprint('web', __name__, template_folder='templates')

@web_bp.route('/')
@login_required
def index():
    """Home page showing all staff"""
    try:
        staff_list = staff_db.get_all_staff(status='active')
        error = None
    except Exception as e:
        error = str(e)
        staff_list = []

    # Group staff by section
    sections = {}
    for staff in staff_list:
        section = staff.get('section', 'Unknown')
        if section not in sections:
            sections[section] = []
        sections[section].append(staff)

    return render_template('index.html', sections=sections, error=error)

@web_bp.route('/search')
@login_required
def search():
    """Search page"""
    query = request.args.get('q', '')

    if query:
        try:
            results = staff_db.search_staff(query)
            error = None
        except Exception as e:
            error = str(e)
            results = []
    else:
        results = []
        error = None

    return render_template('search.html', results=results, query=query, error=error)

@web_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_staff():
    """Add new staff member page"""
    if request.method == 'POST':
        result = staff_db.add_staff(
            name=request.form.get('name', ''),
            position=request.form.get('position', ''),
            section=request.form.get('section', ''),
            extension=request.form.get('extension', ''),
            phone_fixed=request.form.get('phone_fixed', ''),
            phone_mobile=request.form.get('phone_mobile', ''),
            work_email=request.form.get('work_email', ''),
            personal_email=request.form.get('personal_email', ''),
            google_primary_email=request.form.get('google_primary_email', ''),
            zendesk_access='zendesk_access' in request.form,
            buz_access='buz_access' in request.form,
            google_access='google_access' in request.form,
            wiki_access='wiki_access' in request.form,
            voip_access='voip_access' in request.form,
            show_on_phone_list='show_on_phone_list' in request.form,
            include_in_allstaff='include_in_allstaff' in request.form,
            created_by=current_user.email,
            notes=request.form.get('notes', '')
        )

        if 'error' in result:
            sections = staff_db.get_all_sections()
            return render_template('add.html', error=result['error'], sections=sections)

        return redirect(url_for('web.index'))

    sections = staff_db.get_all_sections()
    return render_template('add.html', sections=sections)

@web_bp.route('/edit/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def edit_staff(staff_id):
    """Edit staff member page"""
    if request.method == 'POST':
        result = staff_db.update_staff(
            staff_id=staff_id,
            name=request.form.get('name'),
            position=request.form.get('position'),
            section=request.form.get('section'),
            extension=request.form.get('extension'),
            phone_fixed=request.form.get('phone_fixed'),
            phone_mobile=request.form.get('phone_mobile'),
            work_email=request.form.get('work_email'),
            personal_email=request.form.get('personal_email'),
            google_primary_email=request.form.get('google_primary_email'),
            zendesk_access='zendesk_access' in request.form,
            buz_access='buz_access' in request.form,
            google_access='google_access' in request.form,
            wiki_access='wiki_access' in request.form,
            voip_access='voip_access' in request.form,
            show_on_phone_list='show_on_phone_list' in request.form,
            include_in_allstaff='include_in_allstaff' in request.form,
            status=request.form.get('status', 'active'),
            modified_by=current_user.email,
            notes=request.form.get('notes')
        )

        if 'error' in result:
            staff = staff_db.get_staff_by_id(staff_id)
            sections = staff_db.get_all_sections()
            return render_template('edit.html', staff=staff, error=result['error'], sections=sections)

        return redirect(url_for('web.index'))

    # GET - load the staff member to edit
    staff = staff_db.get_staff_by_id(staff_id)

    if not staff:
        return render_template('edit.html', staff=None, error='Staff member not found', sections=[])

    sections = staff_db.get_all_sections()
    return render_template('edit.html', staff=staff, sections=sections)

@web_bp.route('/delete/<int:staff_id>', methods=['POST'])
@login_required
def delete_staff(staff_id):
    """Delete (deactivate) staff member action"""
    result = staff_db.delete_staff(staff_id)

    if 'error' in result:
        # In a real app, you'd want flash messages
        pass

    return redirect(url_for('web.index'))

@web_bp.route('/sections', methods=['GET'])
@login_required
def sections():
    """Manage sections page"""
    try:
        sections_list = staff_db.get_all_sections()
        error = None
    except Exception as e:
        error = str(e)
        sections_list = []

    return render_template('sections.html', sections=sections_list, error=error)

@web_bp.route('/sections/add', methods=['POST'])
@login_required
def add_section():
    """Add new section"""
    name = request.form.get('name', '').strip()

    if not name:
        return redirect(url_for('web.sections'))

    result = staff_db.add_section(name=name)

    # In a real app, use flash messages for errors
    return redirect(url_for('web.sections'))

@web_bp.route('/sections/<int:section_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_section(section_id):
    """Edit section name"""
    if request.method == 'POST':
        new_name = request.form.get('name', '').strip()

        if new_name:
            result = staff_db.update_section(section_id, name=new_name)

        return redirect(url_for('web.sections'))

    # GET - show the edit form
    sections_list = staff_db.get_all_sections()
    current_section = None

    for section in sections_list:
        if section['id'] == section_id:
            current_section = section
            break

    if not current_section:
        return redirect(url_for('web.sections'))

    return render_template('edit_section.html', section=current_section)

@web_bp.route('/sections/<int:section_id>/delete', methods=['POST'])
@login_required
def delete_section(section_id):
    """Delete section"""
    result = staff_db.delete_section(section_id)

    # In a real app, use flash messages for errors
    return redirect(url_for('web.sections'))
