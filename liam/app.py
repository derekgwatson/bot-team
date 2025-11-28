"""Liam - Buz Leads Monitor."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `liam` imports work
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
liam_dir = Path(__file__).parent
app = Flask(
    __name__,
    template_folder=str(liam_dir / 'web' / 'templates'),
    static_folder=str(liam_dir / 'web' / 'static')
)
app.secret_key = config.secret_key

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
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
        'missing_credentials': len(config.missing_credentials)
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '\U0001F50E',  # magnifying glass tilted right
        'endpoints': {
            'web': {
                '/': 'Dashboard with verification status',
                '/history': 'Verification history'
            },
            'api': {
                'POST /api/leads/verify': 'Run leads verification for all orgs',
                'GET /api/leads/history': 'Get verification history',
                'GET /api/leads/stats': 'Get verification statistics',
                'GET /api/orgs': 'List configured organizations',
                'POST /api/test-connections': 'Test OData connections'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'capabilities': [
            'Monitor Buz OData feeds for leads data',
            'Daily verification that leads are being recorded',
            'Detect OData backup failures via zero-lead alerts',
            'Create Zendesk tickets for IT when issues detected',
            'Dashboard showing verification history'
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
    print("\U0001F50E Hi! I'm Liam")
    print("   Buz Leads Monitor - I check your leads are flowing")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   {org_count} organization(s) configured")
    if config.missing_credentials:
        print(f"   {len(config.missing_credentials)} org(s) need credentials")
        config.print_setup_instructions()
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=True
    )
