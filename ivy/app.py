"""Ivy - Buz Inventory & Pricing Manager."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `ivy` imports work
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
ivy_dir = Path(__file__).parent
app = Flask(
    __name__,
    template_folder=str(ivy_dir / 'web' / 'templates'),
    static_folder=str(ivy_dir / 'web' / 'static')
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

# Initialize sync service
from services.sync_service import init_sync_service
init_sync_service(config)

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
    from database.db import inventory_db
    stats = inventory_db.get_stats()

    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version,
        'configured_orgs': len(config.available_orgs),
        'missing_auth': len(config.buz_orgs_missing_auth),
        'inventory_items': stats['total_inventory_items'],
        'pricing_coefficients': stats['total_pricing_coefficients']
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '\U0001F331',  # seedling - represents inventory/growth
        'endpoints': {
            'web': {
                '/': 'Dashboard with overview statistics',
                '/items': 'List inventory items with filters',
                '/pricing': 'List pricing coefficients with filters',
                '/sync': 'Sync management page',
                '/activity': 'Activity log'
            },
            'api': {
                'GET /api/items': 'List inventory items',
                'GET /api/items/<org>/<group>/<code>': 'Get specific item',
                'GET /api/items/groups': 'List inventory groups',
                'GET /api/items/count': 'Count inventory items',
                'GET /api/pricing': 'List pricing coefficients',
                'GET /api/pricing/<org>/<group>/<code>': 'Get specific coefficient',
                'GET /api/pricing/groups': 'List pricing groups',
                'GET /api/pricing/count': 'Count pricing coefficients',
                'POST /api/sync/inventory': 'Sync inventory from Buz',
                'POST /api/sync/pricing': 'Sync pricing from Buz',
                'POST /api/sync': 'Sync both inventory and pricing',
                'POST /api/sync/all-orgs': 'Sync all organizations',
                'GET /api/sync/status': 'Get sync status',
                'GET /api/sync/history': 'Get sync history',
                'GET /api/orgs': 'List available organizations',
                'GET /api/stats': 'Get statistics',
                'GET /api/activity': 'Get activity log'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'capabilities': [
            'Download inventory items from Buz across all organizations',
            'Download pricing coefficients from Buz across all organizations',
            'Store inventory and pricing data locally for fast access',
            'Track changes between syncs',
            'Provide API for other bots to query items and pricing',
            'Support Buz-Unleashed sync workflows'
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
    print("\U0001F331 Hi! I'm Ivy")
    print("   Buz Inventory & Pricing Manager")
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
