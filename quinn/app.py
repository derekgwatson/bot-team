import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask, jsonify
from config import config
from api.routes import api_bp
from web.simple_routes import simple_web_bp
from services.sync_service import sync_service
import os

app = Flask(__name__)

# Configure Flask for sessions
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Start the sync service
sync_service.interval_seconds = config.sync_interval_seconds
sync_service.start()

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(simple_web_bp, url_prefix='/')

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
        'endpoints': {
            'web': '/',
            'api': '/api',
            'health': '/health'
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👥 Hi! I'm Quinn")
    print("   All-Staff Group Sync Service")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   Syncing with Peter every {config.sync_interval_seconds}s")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
