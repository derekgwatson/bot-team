import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
from services.mavis_service import mavis_service
from database.db import db
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
    Fast by default - use ?detailed=true to include Mavis connection status.
    """
    try:
        response = {
            'status': 'healthy',
            'bot': config.name,
            'version': config.version
        }

        # Only do expensive checks if requested
        if request.args.get('detailed', 'false').lower() == 'true':
            fabric_count = db.get_fabric_count()
            mavis_status = mavis_service.check_connection()

            if not mavis_status.get('connected'):
                response['status'] = 'degraded'

            response['fabric_count'] = fabric_count
            response['mavis'] = {
                'connected': mavis_status.get('connected', False),
                'url': mavis_status.get('url'),
                'product_count': mavis_status.get('product_count')
            }

        return jsonify(response)
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
        'emoji': '🧵',
        'endpoints': {
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'GET /api/fabrics': 'Get a fabric description by code (?code=XXX)',
                'POST /api/fabrics': 'Create or update a fabric description',
                'DELETE /api/fabrics': 'Delete a fabric description',
                'POST /api/fabrics/bulk': 'Bulk lookup or upsert fabrics',
                'GET /api/fabrics/search': 'Search fabrics (?q=XXX)',
                'GET /api/fabrics/stats': 'Get fabric description statistics',
                'GET /api/fabrics/all': 'Get all fabrics with pagination',
                'GET /api/mavis/status': 'Check Mavis connection status',
                'GET /api/mavis/product': 'Get a product from Mavis'
            },
            'system': {
                '/health': 'Health check with Mavis status',
                '/info': 'Bot information'
            }
        },
        'dependencies': ['mavis']
    })


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found'}), 404


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🧵 Hi! I'm Fiona")
    print("   Fabric Description Manager")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
