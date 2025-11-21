import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import warnings
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

import os
from flask import Flask, jsonify
from config import config
from api.deployments import api_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth
from services.deployment_orchestrator import deployment_orchestrator

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
    sally_status = deployment_orchestrator.check_sally_health()
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': '🚀',
        'endpoints': {
            'web': {
                '/': 'Home page with deployment UI'
            },
            'api': {
                'GET /api/dependencies': 'Get bot dependencies',
                'GET /api/dev-config': 'Get development configuration',
                'POST /api/dev-config': 'Update development configuration',
                'GET /api/sally/health': 'Check Sally SSH service health',
                'GET /api/chester/health': 'Check Chester service health',
                'GET /api/bots': 'List all deployable bots',
                'POST /api/verify/<bot_name>': 'Verify bot deployment prerequisites',
                'POST /api/plan/<bot_name>': 'Plan bot deployment',
                'POST /api/deploy/<bot_name>': 'Deploy bot to server',
                'GET /api/deployments': 'List deployment history',
                'GET /api/deployments/<deployment_id>': 'Get deployment details',
                'GET /api/verifications/<verification_id>': 'Get verification results',
                'POST /api/health-check/<bot_name>': 'Check deployed bot health',
                'POST /api/start-service/<bot_name>': 'Start bot service',
                'POST /api/add-bot': 'Add new bot to deployment system',
                'POST /api/restart-dorothy': 'Restart Dorothy service',
                'POST /api/update/<bot_name>': 'Update deployed bot',
                'POST /api/teardown/<bot_name>': 'Remove bot deployment',
                'POST /api/setup-ssl/<bot_name>': 'Setup SSL for bot'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'dependencies': {
            'sally_url': config.sally_url,
            'sally_status': sally_status
        }
    })


if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Hi! I'm Dorothy")
    print("   Deployment Orchestrator")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   Using Sally at {config.sally_url}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
