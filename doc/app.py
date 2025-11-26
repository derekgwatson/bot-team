import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from api.routes import api_bp
from web.routes import web_bp
from database.db import db
from services.checkup import checkup_service
from services.sync import sync_service
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
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure Flask
app.secret_key = config.flask_secret_key

# Register blueprints
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
    Includes basic status info.
    """
    try:
        # Get bot count from registry
        bot_count = db.get_bot_count()

        # Get sync status
        sync_status = sync_service.get_sync_status()

        # Get latest status summary
        statuses = checkup_service.get_latest_status()
        healthy_count = sum(1 for s in statuses if s['status'] == 'healthy')

        return jsonify({
            'status': 'healthy',
            'bot': config.name,
            'version': config.version,
            'registry': {
                'bot_count': bot_count,
                'last_sync': sync_status.get('last_sync')
            },
            'team_status': {
                'healthy': healthy_count,
                'total': len(statuses)
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
        'emoji': '🩺',
        'endpoints': {
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'GET /api/bots': 'List all bots in registry',
                'POST /api/bots/sync': 'Sync bot registry from Chester',
                'GET /api/checkup': 'Run health checkup on all bots',
                'GET /api/checkup/<bot>': 'Check specific bot health',
                'GET /api/status': 'Get latest status for all bots',
                'GET /api/vitals': 'Get team health metrics',
                'GET /api/vitals/<bot>': 'Get specific bot metrics',
                'POST /api/tests/run': 'Run pytest test suite',
                'GET /api/tests/runs': 'Get test run history',
                'GET /api/tests/latest': 'Get most recent test run'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'dependencies': []  # Doc is standalone!
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
    print("🩺 Hi! I'm Doc")
    print("   Bot Team Health Checker")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    # Check if we have bots in registry, suggest sync if not
    if db.get_bot_count() == 0:
        print("📋 No bots in registry yet.")
        print("   Run a sync to populate: POST /api/bots/sync")
        print()

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
