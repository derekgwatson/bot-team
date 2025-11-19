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
from api.bots import bots_bp
from api.deployment import deployment_bp
from web.routes import web_bp

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Register blueprints
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
        'endpoints': {
            'web': '/',
            'api': '/api',
            'health': '/health',
            'info': '/info'
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

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
