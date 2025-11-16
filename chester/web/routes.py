"""Web interface routes for Chester."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.bot_service import bot_service
from services.database import db
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html', config=config)


@web_bp.route('/dashboard')
def dashboard():
    """Interactive dashboard with health checks."""
    # Get all bots
    bots = bot_service.get_all_bots()

    # Check health of all bots
    health_results = bot_service.check_all_bots_health()

    # Create a map of bot_name -> health status
    health_map = {h['bot']: h for h in health_results}

    return render_template(
        'dashboard.html',
        config=config,
        bots=bots,
        health_map=health_map
    )


@web_bp.route('/bot/<bot_name>')
def bot_details(bot_name):
    """Detailed page for a specific bot."""
    bot_info = bot_service.get_bot_info(bot_name)

    if not bot_info:
        return render_template('error.html', error=f'Bot {bot_name} not found'), 404

    # Check health
    health = bot_service.check_bot_health(bot_name)

    return render_template(
        'bot_details.html',
        config=config,
        bot_name=bot_name,
        bot_info=bot_info,
        health=health
    )


@web_bp.route('/search')
def search():
    """Search for bots by capability."""
    query = request.args.get('q', '')

    results = []
    if query:
        results = bot_service.search_bots_by_capability(query)

    return render_template(
        'search.html',
        config=config,
        query=query,
        results=results
    )


@web_bp.route('/new-bot-guide')
def new_bot_guide():
    """Guide for adding a new bot to the team."""
    template_config = config.new_bot_template

    return render_template(
        'new_bot_guide.html',
        config=config,
        template=template_config
    )


@web_bp.route('/manage')
def manage_bots():
    """Manage bot deployment configurations."""
    bots = db.get_all_bots()
    defaults = db.get_deployment_defaults()

    return render_template(
        'manage.html',
        config=config,
        bots=bots,
        defaults=defaults
    )


@web_bp.route('/manage/bot/<bot_name>')
def manage_bot(bot_name):
    """Edit a specific bot's deployment configuration."""
    bot = db.get_bot(bot_name)

    if not bot:
        return render_template('error.html', config=config, error=f'Bot {bot_name} not found'), 404

    defaults = db.get_deployment_defaults()

    return render_template(
        'manage_bot.html',
        config=config,
        bot=bot,
        defaults=defaults
    )


@web_bp.route('/manage/add-bot')
def add_bot_form():
    """Form for adding a new bot."""
    defaults = db.get_deployment_defaults()

    return render_template(
        'add_bot.html',
        config=config,
        defaults=defaults
    )
