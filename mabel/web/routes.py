"""Web interface routes for Mabel."""
from flask import Blueprint, render_template
from flask_login import current_user
from config import Config
from services.auth import login_required

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Main page - simple hello from Mabel."""
    config = Config()
    return render_template('index.html', config=config, current_user=current_user)
