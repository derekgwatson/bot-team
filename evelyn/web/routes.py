"""Web routes for Evelyn - Excel processing UI."""
from flask import Blueprint, render_template
from flask_login import current_user
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Main menu - select which function to use."""
    return render_template(
        'menu.html',
        config=config,
        current_user=current_user
    )


@web_bp.route('/extract-sheets')
@login_required
def extract_sheets():
    """Extract sheets as values - upload and process Excel files."""
    return render_template(
        'extract_sheets.html',
        config=config,
        current_user=current_user
    )
