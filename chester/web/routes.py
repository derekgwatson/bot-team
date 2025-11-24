"""Web interface routes for Chester."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.bot_service import bot_service
from services.database import db
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Main dashboard page."""
    return render_template('index.html', config=config)


@web_bp.route('/dashboard')
@login_required
def dashboard():
    """Interactive dashboard with health checks."""
    # Get all bots
    bots = bot_service.get_all_bots()

    # Check health of all bots (if enabled)
    if config.health_check_enabled:
        health_results = bot_service.check_all_bots_health()
        health_map = {h['bot']: h for h in health_results}
    else:
        # Create a health map with all bots marked as 'disabled'
        health_map = {
            bot_name: {'bot': bot_name, 'status': 'disabled', 'message': 'Health checks disabled'}
            for bot_name in bots.keys()
        }

    return render_template(
        'dashboard.html',
        config=config,
        bots=bots,
        health_map=health_map
    )


@web_bp.route('/public')
@login_required
def public_directory():
    """Public-facing directory - shows only bots marked as public_facing."""
    # Get only public-facing bots from database
    public_bots_db = db.get_public_bots()

    # Get bot metadata from config and merge with database info
    bots_info = []
    for bot_db in public_bots_db:
        bot_name = bot_db['name']
        bot_meta = bot_service.get_bot_info(bot_name)
        if bot_meta:
            # Merge database config with metadata
            bot_combined = {
                **bot_meta,
                'domain': bot_db.get('domain', 'Unknown'),
                'public_facing': bot_db.get('public_facing', False)
            }
            bots_info.append(bot_combined)

    # No health checks here - loaded asynchronously via AJAX
    return render_template(
        'public.html',
        config=config,
        bots=bots_info
    )


@web_bp.route('/bot/<bot_name>')
@login_required
def bot_details(bot_name):
    """Detailed page for a specific bot."""
    bot_info = bot_service.get_bot_info(bot_name)

    if not bot_info:
        return render_template('error.html', config=config, error=f'Bot {bot_name} not found'), 404

    # Check health (if enabled)
    if config.health_check_enabled:
        health = bot_service.check_bot_health(bot_name)
    else:
        health = {'bot': bot_name, 'status': 'disabled', 'message': 'Health checks disabled'}

    return render_template(
        'bot_details.html',
        config=config,
        bot_name=bot_name,
        bot_info=bot_info,
        health=health
    )


@web_bp.route('/search')
@login_required
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
@login_required
def new_bot_guide():
    """Guide for adding a new bot to the team."""
    template_config = config.new_bot_template

    return render_template(
        'new_bot_guide.html',
        config=config,
        template=template_config
    )


@web_bp.route('/manage')
@login_required
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
@login_required
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
@login_required
def add_bot_form():
    """Form for adding a new bot."""
    defaults = db.get_deployment_defaults()

    return render_template(
        'add_bot.html',
        config=config,
        defaults=defaults
    )


@web_bp.route('/network')
@login_required
def network():
    """Interactive network visualization of bot dependencies."""
    return render_template('network.html', config=config)


@web_bp.route('/network/data')
@login_required
def network_data():
    """Get bot network data for visualization (for logged-in web users)."""
    import os
    import yaml
    from pathlib import Path
    from flask import jsonify

    # Get the bot-team directory (parent of chester)
    chester_dir = Path(__file__).resolve().parents[1]
    bot_team_dir = chester_dir.parent

    nodes = []
    edges = []

    # Scan all bot directories
    for bot_path in bot_team_dir.iterdir():
        if not bot_path.is_dir():
            continue

        bot_name = bot_path.name
        config_path = bot_path / 'config.yaml'

        # Skip special directories
        if bot_name in ['shared', 'scripts', 'tests', 'monica-chrome-extension', '.git']:
            continue

        # Skip if no config.yaml
        if not config_path.exists():
            continue

        try:
            # Read the config file
            with open(config_path, 'r') as f:
                bot_config = yaml.safe_load(f)

            if not bot_config:
                continue

            # Extract bot info
            node = {
                'id': bot_name,
                'label': bot_config.get('name', bot_name),
                'description': bot_config.get('description', ''),
                'version': bot_config.get('version', ''),
                'emoji': bot_config.get('emoji', '🤖'),
                'personality': bot_config.get('personality', '')
            }
            nodes.append(node)

            # Extract dependencies and create edges
            dependencies = bot_config.get('dependencies', [])
            for dep in dependencies:
                # Dependencies can be "bot_name # comment" format
                dep_name = dep.split('#')[0].strip() if isinstance(dep, str) else dep
                edges.append({
                    'from': bot_name,
                    'to': dep_name
                })

        except Exception as e:
            # Skip bots with invalid configs
            print(f"Error reading config for {bot_name}: {e}")
            continue

    return jsonify({
        'success': True,
        'nodes': nodes,
        'edges': edges
    })
