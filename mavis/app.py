import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
from services.sync_service import sync_service
from database.db import db
from shared.error_handlers import register_error_handlers
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
# This ensures url_for generates https:// URLs when behind nginx with SSL
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure Flask
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

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



# Register blueprints  # Auth routes at root level (/login, /logout, /auth/callback)
app.register_blueprint(web_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')

# Register error handlers
register_error_handlers(app, logger)


@app.route('/robots.txt')
def robots():
    """Robots.txt to block all search engine crawlers"""
    return """User-agent: *
Disallow: /
""", 200, {'Content-Type': 'text/plain'}


@app.route('/health')
def health():
    """
    Health check endpoint.

    Returns 200 if the app is running.
    Includes sync status for monitoring.
    """
    try:
        sync_status = sync_service.get_status()
        product_count = db.get_product_count()

        # Determine overall health status
        status = 'healthy'
        if sync_status['status'] == 'failed' and sync_status['last_successful_sync_at'] is None:
            status = 'degraded'

        return jsonify({
            'status': status,
            'bot': config.name,
            'version': config.version,
            'product_count': product_count,
            'unleashed_sync': {
                'status': sync_status['status'],
                'last_successful_sync_at': sync_status['last_successful_sync_at'],
                'last_run_started_at': sync_status['last_run_started_at'],
                'last_run_finished_at': sync_status['last_run_finished_at'],
                'last_error': sync_status['last_error']
            }
        })
    except Exception as e:
        logger.exception("Health check error")
        return jsonify({
            'status': 'unhealthy',
            'bot': config.name,
            'version': config.version,
            'error': str(e)
        }), 500


@app.route('/info')
def info():
    """Bot information endpoint"""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': '📦',
        'endpoints': {
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'POST /api/sync/run': 'Trigger a full product sync from Unleashed',
                'GET /api/sync/status': 'Get current sync status',
                'GET /api/sync/history': 'Get sync history',
                'GET /api/products': 'Get a product by code (?code=XXX)',
                'POST /api/products/bulk': 'Bulk lookup products by codes',
                'GET /api/products/changed-since': 'Get products changed since timestamp',
                'GET /api/products/stats': 'Get product statistics'
            },
            'system': {
                '/health': 'Health check with sync status',
                '/info': 'Bot information'
            }
        },
        'dependencies': []  # Mavis has no bot dependencies, only external API
    })


if __name__ == '__main__':
    print("\n" + "="*50)
    print("📦 Hi! I'm Mavis")
    print("   Unleashed Data Integration Bot")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
