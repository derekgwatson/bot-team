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
import os

app = Flask(__name__)

# Sessions / OAuth
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
from web.routes import web_bp
from api.access import api_bp

# Auth (Google OAuth + Flask-Login)

# Register blueprints
app.register_blueprint(web_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')


@app.route('/robots.txt')
def robots():
    """Block search engine crawlers"""
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
        'emoji': config.emoji,
        'endpoints': {
            'web': {
                '/': 'Home page with access request dashboard',
                '/my-access': 'View my access requests',
                '/no-work-google': 'Request non-work Google account (GET/POST)'
            },
            'api': {
                'GET /api/access-requests': 'Get all access requests'
            },
            'auth': {
                '/login': 'Google OAuth login',
                '/auth/callback': 'OAuth callback from Google',
                '/logout': 'Log out the current user'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        }
    })


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🧾 Hi! I'm Rita")
    print("   Access Helper")
    print(f"   Running on http://localhost:{config.server_port}")
    print("=" * 50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
