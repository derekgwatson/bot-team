from flask import Blueprint, render_template, request, redirect, url_for
from services.google_sheets import sheets_service

web_bp = Blueprint('web', __name__, template_folder='templates')

@web_bp.route('/')
def index():
    """Home page showing all contacts"""
    contacts = sheets_service.get_all_contacts()

    if isinstance(contacts, dict) and 'error' in contacts:
        error = contacts['error']
        contacts = []
    else:
        error = None

    # Group contacts by section
    sections = {}
    for contact in contacts:
        section = contact['section']
        if section not in sections:
            sections[section] = []
        sections[section].append(contact)

    return render_template('index.html', sections=sections, error=error)

@web_bp.route('/search')
def search():
    """Search page"""
    query = request.args.get('q', '')

    if query:
        results = sheets_service.search_contacts(query)

        if isinstance(results, dict) and 'error' in results:
            error = results['error']
            results = []
        else:
            error = None
    else:
        results = []
        error = None

    return render_template('search.html', results=results, query=query, error=error)

@web_bp.route('/add', methods=['GET', 'POST'])
def add_contact():
    """Add new contact page"""
    if request.method == 'POST':
        section = request.form.get('section')
        extension = request.form.get('extension')
        name = request.form.get('name')
        position = request.form.get('position')
        fixed_line = request.form.get('fixed_line')
        mobile = request.form.get('mobile')
        email = request.form.get('email')

        result = sheets_service.add_contact(
            section=section,
            extension=extension or '',
            name=name,
            position=position or '',
            fixed_line=fixed_line or '',
            mobile=mobile or '',
            email=email or ''
        )

        if isinstance(result, dict) and 'error' in result:
            return render_template('add.html', error=result['error'])

        return redirect(url_for('web.index'))

    return render_template('add.html')

@web_bp.route('/edit/<int:row>', methods=['GET', 'POST'])
def edit_contact(row):
    """Edit contact page"""
    if request.method == 'POST':
        extension = request.form.get('extension')
        name = request.form.get('name')
        position = request.form.get('position')
        fixed_line = request.form.get('fixed_line')
        mobile = request.form.get('mobile')
        email = request.form.get('email')

        result = sheets_service.update_contact(
            row_number=row,
            extension=extension or '',
            name=name,
            position=position or '',
            fixed_line=fixed_line or '',
            mobile=mobile or '',
            email=email or ''
        )

        if isinstance(result, dict) and 'error' in result:
            # Get the contact again to re-populate the form
            contacts = sheets_service.get_all_contacts()
            contact = None
            if not isinstance(contacts, dict):
                for c in contacts:
                    if c['row'] == row:
                        contact = c
                        break
            return render_template('edit.html', contact=contact, error=result['error'])

        return redirect(url_for('web.index'))

    # GET - load the contact to edit
    contacts = sheets_service.get_all_contacts()

    if isinstance(contacts, dict) and 'error' in contacts:
        return render_template('edit.html', contact=None, error=contacts['error'])

    # Find the contact with this row number
    contact = None
    for c in contacts:
        if c['row'] == row:
            contact = c
            break

    if not contact:
        return render_template('edit.html', contact=None, error='Contact not found')

    return render_template('edit.html', contact=contact)

@web_bp.route('/delete/<int:row>', methods=['POST'])
def delete_contact(row):
    """Delete contact action"""
    result = sheets_service.delete_contact(row)

    if isinstance(result, dict) and 'error' in result:
        # In a real app, you'd want flash messages
        pass

    return redirect(url_for('web.index'))
