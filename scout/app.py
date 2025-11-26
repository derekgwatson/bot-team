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
from services.checker import checker
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
    Includes bot connectivity status for monitoring.
    """
    try:
        # Get issue stats
        issue_stats = db.get_issue_stats()

        # Get last check run
        last_run = db.get_last_check_run()

        # Check bot connectivity
        try:
            bot_status = checker.get_bot_status()
            all_connected = all(s.get('connected', False) for s in bot_status.values())
        except Exception:
            bot_status = {}
            all_connected = False

        # Determine overall health status
        status = 'healthy'
        if not all_connected:
            status = 'degraded'  # Still functional, but some bots unreachable
        if last_run and last_run.get('status') == 'failed':
            status = 'degraded'

        return jsonify({
            'status': status,
            'bot': config.name,
            'version': config.version,
            'issues': {
                'open': issue_stats.get('open', 0),
                'total': issue_stats.get('total', 0)
            },
            'last_check': {
                'status': last_run.get('status') if last_run else None,
                'started_at': last_run.get('started_at') if last_run else None
            },
            'bots': {
                name: {'connected': s.get('connected', False)}
                for name, s in bot_status.items()
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
        'emoji': '🔭',
        'endpoints': {
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'POST /api/checks/run': 'Trigger a check run (called by Skye)',
                'GET /api/checks/status': 'Get last run status',
                'GET /api/checks/history': 'Get check run history',
                'GET /api/issues': 'Get tracked issues',
                'GET /api/issues/stats': 'Get issue statistics',
                'POST /api/issues/<type>/<key>/resolve': 'Resolve an issue',
                'GET /api/bots/status': 'Get status of dependent bots'
            },
            'system': {
                '/health': 'Health check with bot status',
                '/info': 'Bot information'
            }
        },
        'dependencies': ['mavis', 'fiona', 'sadie']
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
    print("🔭 Hi! I'm Scout")
    print("   System Monitoring Bot")
    print(f"   Running on http://localhost:{config.server_port}")
    print("   Scheduling managed by Skye")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
