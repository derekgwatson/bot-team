"""
Juno - Customer Tracking Experience Bot
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

from juno.config import config
from juno.api.routes import api_bp
from juno.web.routes import web_bp

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

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp, url_prefix='/')


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
                '/track/<code>': 'Customer tracking page'
            },
            'api': {
                'POST /api/tracking-links': 'Create new tracking link',
                'GET /api/tracking-links': 'List active tracking links',
                'GET /api/tracking-links/<code>': 'Get tracking link details',
                'GET /api/tracking-links/<code>/location': 'Get current location',
                'PUT /api/tracking-links/<code>/arrived': 'Mark as arrived',
                'PUT /api/tracking-links/<code>/cancel': 'Cancel tracking link'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'integration': {
            'travis': config.travis_base_url,
            'note': 'Juno calls Travis to get privacy-aware staff locations'
        }
    })


@app.route('/robots.txt')
def robots():
    """Block search engine crawlers"""
    return "User-agent: *\nDisallow: /\n", 200, {'Content-Type': 'text/plain'}


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
    print(f"{config.emoji} Hi! I'm {config.name.title()}")
    print(f"   {config.description}")
    print(f"   Version: {config.version}")
    print(f"   Running on http://{config.server_host}:{config.server_port}")
    print("="*60)
    print("\nEndpoints:")
    print(f"  • Track Page: http://localhost:{config.server_port}/track/<code>")
    print(f"  • API Info:   http://localhost:{config.server_port}/info")
    print(f"  • Health:     http://localhost:{config.server_port}/health")
    print("="*60)
    print(f"\nIntegration:")
    print(f"  • Travis URL: {config.travis_base_url}")
    print("="*60 + "\n")

    # Run the Flask development server
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
