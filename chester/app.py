"""Chester - Bot Team Concierge."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `chester` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
from flask import Flask, jsonify
from config import config
from services.auth import init_auth
from api.bots import bots_bp
from api.deployment import deployment_bp
from web.routes import web_bp
from web.auth_routes import auth_bp

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(bots_bp, url_prefix='/api')
app.register_blueprint(deployment_bp, url_prefix='/api')
app.register_blueprint(web_bp)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '🎩',
        'endpoints': {
            'web': {
                '/': 'Home page (redirects to dashboard)',
                '/dashboard': 'Bot dashboard with status overview',
                '/public': 'Public bot directory (no auth required)',
                '/bot/<bot_name>': 'Individual bot details page',
                '/search': 'Search bots by name or capability',
                '/new-bot-guide': 'Guide for creating new bots',
                '/manage': 'Bot management interface (admin)',
                '/manage/bot/<bot_name>': 'Edit bot configuration',
                '/manage/add-bot': 'Add new bot to system'
            },
            'api': {
                'GET /api/bots': 'List all bots',
                'GET /api/bots/<bot_name>': 'Get bot details',
                'GET /api/health/all': 'Health check all bots',
                'GET /api/health/<bot_name>': 'Health check specific bot',
                'GET /api/health/public/all': 'Public health status (no auth)',
                'GET /api/capabilities/<bot_name>': 'Get bot capabilities',
                'GET /api/search': 'Search bots by query',
                'GET /api/summary': 'Bot team summary statistics',
                'GET /api/deployment/bots': 'List deployment configurations',
                'GET /api/deployment/bots/<bot_name>': 'Get bot deployment config',
                'POST /api/deployment/bots': 'Create deployment configuration',
                'PUT /api/deployment/bots/<bot_name>': 'Update deployment config',
                'DELETE /api/deployment/bots/<bot_name>': 'Delete deployment config',
                'GET /api/deployment/defaults': 'Get default deployment settings',
                'PUT /api/deployment/defaults': 'Update default deployment settings'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        }
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎩 Hi! I'm Chester")
    print("   Bot Team Concierge")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    # Sync bots from config.yaml to database on startup
    from services.database import db
    print("🔄 Syncing bots from config.yaml to database...")
    result = db.sync_bots_from_config(verbose=True)
    if result['added']:
        print(f"   Added: {', '.join(result['added'])}")
    print()

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
