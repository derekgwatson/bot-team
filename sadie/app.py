import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from config import config
from shared.auth import GatewayAuth
from api.routes import api_bp
from web.routes import web_bp
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
                '/': 'Ticket dashboard with filtering',
                '/ticket/{id}': 'View specific ticket details',
                '/user/{id}/tickets': 'View all tickets for a user',
                '/organization/{id}/tickets': 'View all tickets for an organization'
            },
            'api': {
                'GET /api/tickets': 'List tickets with optional filters (status, priority, group)',
                'POST /api/tickets': 'Create a new Zendesk ticket',
                'GET /api/tickets/{id}': 'Get specific ticket details',
                'GET /api/tickets/{id}/comments': 'Get all comments for a ticket',
                'GET /api/tickets/search': 'Search tickets by subject or content',
                'GET /api/users/{id}/tickets': 'Get all tickets for a user',
                'GET /api/organizations/{id}/tickets': 'Get all tickets for an organization',
                'GET /api/groups': 'Get all Zendesk groups for filtering'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'zendesk': {
            'subdomain': config.zendesk_subdomain or 'Not configured',
            'authentication': 'Required for all web and API endpoints'
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎫 Hi! I'm Sadie")
    print("   Zendesk Ticket Information")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
