import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from config import config
from api.routes import api_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth
import os

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
        'emoji': '🏢',
        'endpoints': {
            'web': {
                '/': 'Dashboard with onboarding form and requests',
                '/onboard/new': 'New onboarding form',
                '/onboard/<id>': 'View onboarding request details',
                '/tasks': 'View pending manual tasks',
                '/requests': 'View all onboarding requests'
            },
            'api': {
                'GET /api/intro': 'Bot introduction and capabilities',
                'POST /api/onboard': 'Submit a new onboarding request',
                'GET /api/onboard': 'List all onboarding requests',
                'GET /api/onboard/<id>': 'Get onboarding request details',
                'POST /api/onboard/<id>/start': 'Start onboarding workflow',
                'GET /api/tasks': 'Get pending manual tasks',
                'POST /api/tasks/<id>/complete': 'Mark manual task as complete',
                'GET /api/stats': 'Get onboarding statistics',
                'GET /api/dependencies': 'Get bot dependencies',
                'GET /api/dev-config': 'Get dev bot configuration',
                'POST /api/dev-config': 'Update dev bot configuration'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'dependencies': ['fred', 'zac', 'peter', 'sadie']
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎉 Hi! I'm Oscar")
    print("   Staff Onboarding Orchestrator")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
