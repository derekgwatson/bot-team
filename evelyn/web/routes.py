"""Web routes for Evelyn - Excel processing UI."""
from flask import Blueprint, render_template
from flask_login import current_user
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Main page - upload and process Excel files."""
    return render_template(
        'index.html',
        config=config,
        current_user=current_user
    )
