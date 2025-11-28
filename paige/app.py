"""Paige - DokuWiki User Manager for the bot team."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `paige` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
from shared.error_handlers import register_error_handlers
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, template_folder='web/templates')
app.secret_key = config.secret_key

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
# This ensures url_for generates https:// URLs when behind nginx with SSL
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication via Chester's gateway
auth = GatewayAuth(app, config)

# Store auth instance in services.auth for backward compatibility with routes
import services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user

# Import blueprints AFTER auth is initialized (they use @login_required decorator)
from api.routes import api_bp
from web.routes import web_bp

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp)

# Register error handlers
register_error_handlers(app, logger)


@app.route('/health')
def health():
    """Health check endpoint."""
    from services.dokuwiki_service import DokuWikiService

    wiki_service = DokuWikiService(
        dokuwiki_path=config.dokuwiki_path,
        default_groups=config.default_groups
    )
    wiki_health = wiki_service.get_health_status()

    return jsonify({
        'status': 'healthy' if wiki_health['healthy'] else 'degraded',
        'bot': config.name,
        'version': config.version,
        'dokuwiki': {
            'path': wiki_health['dokuwiki_path'],
            'healthy': wiki_health['healthy'],
            'user_count': wiki_health['user_count']
        }
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '\U0001F4D6',  # Open book emoji
        'endpoints': {
            'web': {
                '/': 'Dashboard with user list and management',
            },
            'api': {
                'GET /api/users': 'List all wiki users',
                'GET /api/users/<login>': 'Get user by login',
                'POST /api/users': 'Create new user',
                'DELETE /api/users/<login>': 'Delete user',
                'GET /api/users/<login>/exists': 'Check if user exists',
                'GET /api/status': 'Get service status'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        }
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("\U0001F4D6 Hi! I'm Paige")
    print("   DokuWiki User Manager")
    print(f"   Running on http://localhost:{config.server_port}")
    print("=" * 50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
