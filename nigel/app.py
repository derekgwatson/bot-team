import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
from flask import Flask, jsonify
from config import config
from api.routes import api_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth

app = Flask(__name__)

# Configure Flask for sessions and OAuth
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/')
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
                '/': 'Dashboard - overview of monitored quotes',
                '/quotes': 'List all monitored quotes',
                '/quotes/add': 'Add a new quote to monitor',
                '/quotes/<quote_id>': 'View quote details and history',
                '/history': 'View all price check history',
                '/discrepancies': 'View price discrepancies'
            },
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'GET /api/quotes': 'List all monitored quotes',
                'POST /api/quotes': 'Add a quote to monitor',
                'GET /api/quotes/<quote_id>': 'Get quote details',
                'DELETE /api/quotes/<quote_id>': 'Remove quote from monitoring',
                'POST /api/quotes/<quote_id>/activate': 'Reactivate monitoring',
                'POST /api/quotes/<quote_id>/deactivate': 'Pause monitoring',
                'POST /api/quotes/check': 'Check price for a single quote',
                'POST /api/quotes/check-all': 'Check prices for all active quotes',
                'GET /api/history': 'Get price check history',
                'GET /api/discrepancies': 'Get detected discrepancies',
                'POST /api/discrepancies/<id>/resolve': 'Mark discrepancy as resolved',
                'GET /api/stats': 'Get monitoring statistics'
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
    print("\n" + "=" * 50)
    print("  Nigel - Quote Price Monitor")
    print("  " + config.description)
    print(f"  Running on http://localhost:{config.server_port}")
    print("=" * 50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
