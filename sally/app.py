import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import warnings
from cryptography.utils import CryptographyDeprecationWarning

warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from api.execute import api_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth
import os

app = Flask(__name__)

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp)  # Auth routes at root level (/login, /logout, /auth/callback)
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
                '/': 'Home page with server list and command executor'
            },
            'api': {
                'GET /api/servers': 'List all configured servers',
                'GET /api/test/<server_name>': 'Test connection to a server',
                'POST /api/execute': 'Execute a command on a remote server',
                'GET /api/history': 'Get command execution history',
                'GET /api/history/<exec_id>': 'Get details of a specific execution'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information',
                '/robots.txt': 'Robots.txt file'
            }
        },
        'ssh': {
            'default_user': config.ssh_default_user,
            'connect_timeout': f'{config.ssh_connect_timeout}s',
            'command_timeout': f'{config.ssh_command_timeout}s',
            'configured_servers': len(config.servers)
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👩‍💼 Hi! I'm Sally")
    print("   SSH Command Executor")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
