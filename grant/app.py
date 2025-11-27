"""Grant - Centralized Authorization Manager."""
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
from shared.error_handlers import register_error_handlers
from database.db import init_db
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='web/templates')

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure Flask
app.secret_key = config.secret_key

# Initialize database
init_db(str(config.database_path))

# Initialize authentication via Chester's gateway
# Grant uses admin_only mode - only superadmins can access the UI
auth = GatewayAuth(app, config)

# Store auth instance in services.auth for backward compatibility with routes
import services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user

# Import blueprints AFTER auth is initialized
from api.routes import api_bp
from web.routes import web_bp

# Register blueprints
app.register_blueprint(web_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')

# Register error handlers
register_error_handlers(app, logger)


@app.route('/robots.txt')
def robots():
    """Robots.txt to block all search engine crawlers."""
    return """User-agent: *
Disallow: /
""", 200, {'Content-Type': 'text/plain'}


@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        from database.db import get_db
        db = get_db()
        stats = db.get_stats()

        return jsonify({
            'status': 'healthy',
            'bot': config.name,
            'version': config.version,
            'permissions': stats['total_permissions'],
            'users': stats['unique_users']
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
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': '🔐',
        'endpoints': {
            'web': {
                'GET /': 'Dashboard',
                'GET /users': 'List users',
                'GET /bots': 'List bots',
                'GET /audit': 'Audit log',
                'GET /grant': 'Grant access form'
            },
            'api': {
                'GET /api/access': 'Check user access to bot',
                'GET /api/permissions': 'List permissions',
                'POST /api/permissions': 'Grant permission',
                'DELETE /api/permissions': 'Revoke permission',
                'GET /api/users': 'List users',
                'GET /api/bots': 'List bots',
                'POST /api/bots/sync': 'Sync from Chester',
                'GET /api/audit': 'Get audit log',
                'GET /api/stats': 'Get statistics'
            },
            'system': {
                'GET /health': 'Health check',
                'GET /info': 'Bot information'
            }
        }
    })


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🔐 Hi! I'm Grant")
    print("   Centralized Authorization Manager")
    print(f"   Running on http://localhost:{config.server_port}")
    print("=" * 50 + "\n")

    # Sync bots from Chester on startup if configured
    if config.sync_bots_from_chester:
        try:
            from services.permissions import permission_service
            result = permission_service.sync_bots_from_chester()
            if result['success']:
                logger.info(f"Synced {result['synced']} bots from Chester on startup")
            else:
                logger.warning(f"Failed to sync bots on startup: {result.get('error')}")
        except Exception as e:
            logger.warning(f"Could not sync bots on startup: {e}")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
