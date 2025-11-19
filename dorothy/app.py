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
        'sally_url': config.sally_url,
        'sally_status': sally_status,
        'endpoints': {
            'web': '/',
            'api': '/api',
            'health': '/health',
            'sally_health': '/api/sally/health'
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
        debug=True
    )
