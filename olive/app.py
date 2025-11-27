import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `olive` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
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

# Configure Flask for sessions and OAuth
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
# This ensures url_for generates https:// URLs when behind nginx with SSL
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp, url_prefix='/')

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
        'emoji': '📞',
        'endpoints': {
            'web': {
                '/': 'Dashboard with offboarding form and requests',
                '/offboard/new': 'New offboarding form',
                '/offboard/{id}': 'View offboarding request details',
                '/tasks': 'View pending manual tasks',
                '/requests': 'View all offboarding requests'
            },
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'POST /api/offboard': 'Submit a new offboarding request',
                'GET /api/offboard': 'List all offboarding requests',
                'GET /api/offboard/{id}': 'Get offboarding request details',
                'POST /api/offboard/{id}/start': 'Start offboarding workflow',
                'GET /api/tasks': 'Get pending manual tasks',
                'POST /api/tasks/{id}/complete': 'Mark manual task as complete',
                'GET /api/stats': 'Get offboarding statistics',
                'GET /api/dependencies': 'Get bot dependencies',
                'GET /api/dev-config': 'Get dev bot configuration',
                'POST /api/dev-config': 'Update dev bot configuration'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'dependencies': ['peter', 'fred', 'zac', 'sadie']
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🫒 Hi! I'm Olive")
    print("   Staff Offboarding Orchestrator")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
