"""Web routes for Banji."""
from flask import Blueprint, render_template
from config import config
from services.auth import login_required

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
@login_required
def index():
    """Banji home page."""
    return render_template(
        'index.html',
        bot_name=config.name,
        description=config.description,
        personality=config.personality,
        browser_mode='headless' if config.browser_headless else 'headed',
        buz_url='https://go.buzmanager.com',
        active_orgs=', '.join(config.buz_orgs.keys()) if config.buz_orgs else 'None configured',
        is_fully_configured=config.is_fully_configured,
        setup_instructions=config.setup_instructions
    )
