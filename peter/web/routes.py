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
        fixed_line = request.form.get('fixed_line')
        mobile = request.form.get('mobile')
        email = request.form.get('email')

        result = sheets_service.add_contact(
            section=section,
            extension=extension,
            name=name,
            fixed_line=fixed_line or '',
            mobile=mobile or '',
            email=email or ''
        )

        if isinstance(result, dict) and 'error' in result:
            return render_template('add.html', error=result['error'])

        return redirect(url_for('web.index'))

    return render_template('add.html')

@web_bp.route('/delete/<int:row>', methods=['POST'])
def delete_contact(row):
    """Delete contact action"""
    result = sheets_service.delete_contact(row)

    if isinstance(result, dict) and 'error' in result:
        # In a real app, you'd want flash messages
        pass

    return redirect(url_for('web.index'))
