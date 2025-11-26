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
from api.contacts import api_bp
from web.routes import web_bp



# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
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
                '/': 'Staff directory home page',
                '/search': 'Search for staff members',
                '/add': 'Add new staff member',
                '/edit/{id}': 'Edit staff member details',
                '/sections': 'Manage sections/departments'
            },
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'GET /api/contacts': 'Get phone list contacts (legacy)',
                'GET /api/contacts/search': 'Search contacts (legacy)',
                'POST /api/contacts': 'Add new contact (legacy)',
                'PUT /api/contacts/{id}': 'Update contact (legacy)',
                'DELETE /api/contacts/{id}': 'Delete contact (legacy)',
                'GET /api/staff': 'Get all staff members',
                'POST /api/staff': 'Create new staff member',
                'GET /api/staff/{id}': 'Get specific staff member',
                'PATCH /api/staff/{id}': 'Update staff member',
                'GET /api/staff/allstaff-members': 'Get all-staff group emails',
                'POST /api/access-requests': 'Submit access request',
                'GET /api/access-requests': 'Get access requests',
                'GET /api/access-requests/{id}': 'Get specific access request',
                'POST /api/access-requests/{id}/approve': 'Approve access request',
                'POST /api/access-requests/{id}/deny': 'Deny access request',
                'GET /api/is-approved': 'Check if email is approved'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👔 Hi! I'm Peter")
    print("   Staff Directory")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
