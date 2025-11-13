from flask import Blueprint, render_template, request, session, redirect, url_for
from functools import wraps
from services.peter_client import peter_client

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
    """Display the phone directory"""
    contacts = peter_client.get_all_contacts()

    if isinstance(contacts, dict) and 'error' in contacts:
        return render_template('index.html', error=contacts['error'], sections=None)

    # Group contacts by section
    sections = peter_client.group_by_section(contacts)

    return render_template('index.html', sections=sections, error=None)

@web_bp.route('/search')
@require_auth
def search():
    """Search for contacts"""
    query = request.args.get('q', '')

    if not query:
        return render_template('search.html', results=None, query='')

    results = peter_client.search_contacts(query)

    if isinstance(results, dict) and 'error' in results:
        return render_template('search.html', error=results['error'], results=None, query=query)

    # Group results by section
    sections = peter_client.group_by_section(results)

    return render_template('search.html', sections=sections, query=query, error=None)
