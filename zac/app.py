import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from config import config
from shared.auth import GatewayAuth
import os

app = Flask(__name__)

# Configure Flask for sessions and OAuth
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
from api.operations import operations_bp
from web.routes import web_bp



# Register blueprints
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
                '/': 'Main dashboard - list all Zendesk users',
                '/user/{user_id}': 'View detailed information about a specific user',
                '/user/create': 'Create a new Zendesk user (GET/POST)',
                '/user/{user_id}/edit': 'Edit an existing user (GET/POST)',
                '/user/{user_id}/suspend': 'Suspend a user (POST)',
                '/user/{user_id}/unsuspend': 'Unsuspend a user (POST)',
                '/user/{user_id}/delete': 'Delete a user (POST)'
            },
            'api': {
                'GET /api/users': 'List all Zendesk users with optional filtering (role, page, per_page)',
                'GET /api/users/{user_id}': 'Get a specific user by ID',
                'GET /api/users/search': 'Search for users by name or email',
                'POST /api/users': 'Create a new Zendesk agent (immediate)',
                'PUT/PATCH /api/users/{user_id}': 'Update a user\'s properties',
                'POST /api/users/{user_id}/suspend': 'Suspend a user (immediate)',
                'POST /api/users/{user_id}/unsuspend': 'Unsuspend a user (immediate)',
                'DELETE /api/users/{user_id}': 'Delete a user (immediate)'
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
                '/auth/callback': 'OAuth callback from Google',
                '/logout': 'Log out the current user'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information',
                '/robots.txt': 'Robots.txt file'
            }
        },
        'authentication': {
            'provider': 'Google OAuth',
            'required': 'All web routes require authentication',
            'admin_emails': len(config.admin_emails) if hasattr(config, 'admin_emails') else 0
        },
        'zendesk': {
            'subdomain': config.zendesk_subdomain if config.zendesk_subdomain else 'Not configured'
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👤 Hi! I'm Zac")
    print("   Zendesk User Management")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
