"""
Monica - ChromeOS Monitoring Agent
Flask application entry point
"""

import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import logging
from flask import Flask, jsonify

from monica.config import config
from monica.database.db import db
from shared.auth import GatewayAuth

# Configure logging based on config
log_level_name = config.log_level.upper()
log_level = getattr(logging, log_level_name, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Log the current log level on startup
logger.info(f"Logging configured at {log_level_name} level")

# Initialize Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Initialize authentication via Chester's gateway
# MUST happen before importing blueprints that use @login_required
auth = GatewayAuth(app, config)

# Store auth instance in monica.services.auth for backward compatibility with routes
import monica.services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user

# Import blueprints AFTER auth is initialized (they use @login_required decorator)
from monica.api.routes import api_bp
from monica.web.routes import web_bp

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp, url_prefix='/')

# Note: Registration code cleanup removed - pending devices are now shown on
# the dashboard and users delete them directly if not needed


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version
    })


@app.route('/info')
def info():
    """Bot information endpoint"""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': config.emoji,
        'endpoints': {
            'web': {
                '/': 'Home page',
                '/dashboard': 'Device dashboard',
                '/agent': 'Agent page (requires ?store=X&device=Y params)'
            },
            'api': {
                'POST /api/register': 'Register a new device',
                'POST /api/heartbeat': 'Record device heartbeat',
                'GET /api/devices': 'List all devices',
                'GET /api/devices/{id}/heartbeats': 'Get device heartbeat history'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'thresholds': {
            'online': f'<= {config.online_threshold} minutes',
            'degraded': f'{config.online_threshold}-{config.degraded_threshold} minutes',
            'offline': f'> {config.degraded_threshold} minutes'
        }
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'The requested resource was not found on this server.',
        'hint': 'Visit /info for available endpoints'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred. Please try again later.'
    }), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print(f"📡 Hi! I'm {config.name.title()}")
    print(f"   {config.description}")
    print(f"   Version: {config.version}")
    print(f"   Running on http://{config.server_host}:{config.server_port}")
    print("="*60)
    print("\nEndpoints:")
    print(f"  • Dashboard:  http://localhost:{config.server_port}/dashboard")
    print(f"  • Agent Page: http://localhost:{config.server_port}/agent?store=XXX&device=YYY")
    print(f"  • API Info:   http://localhost:{config.server_port}/info")
    print(f"  • Health:     http://localhost:{config.server_port}/health")
    print("="*60 + "\n")

    # Run the Flask development server
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
