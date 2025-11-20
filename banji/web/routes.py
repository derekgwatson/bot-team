"""Web routes for Banji."""
from flask import Blueprint, render_template
from config import config

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Banji home page."""
    return render_template(
        'index.html',
        bot_name=config.name,
        description=config.description,
        personality=config.personality,
        browser_mode='headless' if config.browser_headless else 'headed',
        buz_url='https://go.buzmanager.com',
        active_orgs=', '.join(config.buz_orgs.keys())
    )
