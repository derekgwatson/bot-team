"""Web interface routes for Mabel."""
from flask import Blueprint, render_template
from config import Config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
def index():
    """Main page - simple hello from Mabel."""
    config = Config()
    return render_template('index.html', config=config)
