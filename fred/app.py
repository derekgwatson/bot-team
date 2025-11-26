import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from api.users import api_bp
from api.operations import operations_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth

app = Flask(__name__)

# Configure Flask for sessions and OAuth
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(operations_bp, url_prefix='/api')
app.register_blueprint(web_bp, url_prefix='/')

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
        'emoji': config.emoji,
        'endpoints': {
            'web': {
                '/': 'Home page - Active users list',
                '/archived': 'Archived users list',
                '/users/{email}': 'User detail page',
                '/users/new': 'Create new user form'
            },
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'GET /api/users': 'List all users (params: archived, max_results)',
                'GET /api/users/{email}': 'Get specific user details',
                'POST /api/users': 'Create new user (immediate)',
                'POST /api/users/{email}/archive': 'Archive user (immediate)',
                'DELETE /api/users/{email}': 'Permanently delete user (immediate)'
            },
            'operations': {
                'GET /api/operations': 'List queued operations (params: status, type, limit)',
                'GET /api/operations/{id}': 'Get operation details',
                'POST /api/operations': 'Queue an operation for later execution',
                'POST /api/operations/{id}/execute': 'Execute a pending operation',
                'DELETE /api/operations/{id}': 'Cancel a pending operation',
                'GET /api/operations/by-reference/{ref}': 'Get operations by external reference'
            },
            'auth': {
                '/login': 'Google OAuth login',
                '/auth/callback': 'OAuth callback handler',
                '/logout': 'Logout current user'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information',
                '/robots.txt': 'Search engine crawler rules'
            }
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👤 Hi! I'm Fred")
    print("   Google Workspace User Manager")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
