"""
Travis - Field Staff Location Tracking Bot
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
from werkzeug.middleware.proxy_fix import ProxyFix

from travis.config import config
from travis.api.routes import api_bp
from travis.web.routes import web_bp
from travis.web.auth_routes import auth_bp
from travis.services.auth import init_auth
from shared.error_handlers import register_error_handlers

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
app = Flask(__name__,
            template_folder='web/templates',
            static_folder='web/static')
app.secret_key = config.secret_key

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp)  # Auth routes at root level (/login, /logout, /auth/callback)
app.register_blueprint(web_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')

# Register error handlers
register_error_handlers(app, logger)


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
            'api': {
                'POST /api/location': 'Record GPS location ping from device',
                'GET /api/location/<staff_id>': 'Get shareable location (privacy-aware)',
                'GET /api/staff': 'List all staff',
                'POST /api/staff': 'Create new staff member',
                'GET /api/staff/<id>': 'Get staff details',
                'PUT /api/staff/<id>/status': 'Update staff status',
                'POST /api/staff/<id>/token': 'Regenerate device token',
                'POST /api/journeys': 'Create new journey',
                'GET /api/journeys/<id>': 'Get journey details',
                'PUT /api/journeys/<id>/start': 'Start a journey',
                'PUT /api/journeys/<id>/arrive': 'Mark journey arrived',
                'PUT /api/journeys/<id>/complete': 'Complete journey',
                'GET /api/journeys/<id>/pings': 'Get journey location history',
                'GET /api/journeys/by-reference/<ref>': 'Get journey by job reference'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'privacy': {
            'share_only_in_transit': config.share_only_in_transit,
            'customer_proximity_buffer_meters': config.customer_proximity_buffer,
            'note': 'Location coordinates are only shared when staff status is "in_transit". '
                    'When at another customer, only a status message is returned to protect privacy.'
        },
        'status_values': config.status_values
    })


@app.route('/robots.txt')
def robots():
    """Block search engine crawlers"""
    return "User-agent: *\nDisallow: /\n", 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    print("\n" + "="*60)
    print(f"{config.emoji} Hi! I'm {config.name.title()}")
    print(f"   {config.description}")
    print(f"   Version: {config.version}")
    print(f"   Running on http://{config.server_host}:{config.server_port}")
    print("="*60)
    print("\nEndpoints:")
    print(f"  • API Info:   http://localhost:{config.server_port}/info")
    print(f"  • Health:     http://localhost:{config.server_port}/health")
    print(f"  • Location:   POST http://localhost:{config.server_port}/api/location")
    print(f"  • Staff:      http://localhost:{config.server_port}/api/staff")
    print("="*60)
    print("\nPrivacy Mode:")
    print(f"  • Only shares location when staff is 'in_transit'")
    print(f"  • Hides exact location when 'at_customer'")
    print("="*60 + "\n")

    # Run the Flask development server
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
