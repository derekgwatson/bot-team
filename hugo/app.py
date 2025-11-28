"""Hugo - Buz User Management Bot."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `hugo` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import logging
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
from shared.error_handlers import register_error_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with template folder
hugo_dir = Path(__file__).parent
app = Flask(
    __name__,
    template_folder=str(hugo_dir / 'web' / 'templates'),
    static_folder=str(hugo_dir / 'web' / 'static')
)
app.secret_key = config.secret_key

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
# This ensures url_for generates https:// URLs when behind nginx with SSL
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication via Chester's gateway
# MUST happen before importing blueprints that use @login_required
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
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version,
        'configured_orgs': len(config.available_orgs),
        'missing_auth': len(config.buz_orgs_missing_auth)
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '\U0001F50D',  # magnifying glass
        'endpoints': {
            'web': {
                '/': 'Dashboard with user statistics',
                '/users': 'List all users with filters',
                '/users/<email>': 'User detail page with edit modal',
                '/activity': 'Activity log',
                '/sync': 'Sync history'
            },
            'api': {
                'GET /api/users': 'List cached users',
                'GET /api/users/<email>': 'Get user by email',
                'GET /api/users/<email>/details': 'Get editable user details from Buz',
                'PATCH /api/users/<email>': 'Update user details in Buz',
                'POST /api/users/sync': 'Sync users from Buz',
                'POST /api/users/<email>/activate': 'Activate user in Buz',
                'POST /api/users/<email>/deactivate': 'Deactivate user in Buz',
                'GET /api/orgs': 'List available organizations',
                'GET /api/groups': 'Get available user groups for an org',
                'GET /api/customers/search': 'Search for customers by company name',
                'GET /api/customers/from-user': 'Get customer from existing user',
                'GET /api/sync/status': 'Get sync status',
                'GET /api/sync/history': 'Get sync history',
                'GET /api/activity': 'Get activity log',
                'GET /api/stats': 'Get user statistics'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'capabilities': [
            'Cache Buz users locally for fast lookups',
            'Sync users from Buz across multiple organizations',
            'Activate/deactivate users in Buz',
            'Edit user details (name, phone, group)',
            'Assign customers to customer users',
            'Search for customers by company name',
            'Track access changes with activity log',
            'Sync access changes to Peter (staff database)',
            'Web UI for user management'
        ],
        'configured_orgs': config.available_orgs
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    org_count = len(config.available_orgs)
    print("\n" + "="*50)
    print("\U0001F50D Hi! I'm Hugo")
    print("   Buz User Management - I know who has access")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   {org_count} organization(s) configured")
    if config.buz_orgs_missing_auth:
        print(f"   {len(config.buz_orgs_missing_auth)} org(s) need auth setup")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=True  # Allow concurrent requests
    )
