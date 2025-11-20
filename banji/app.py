"""Banji - Playwright Browser Automation for Buz."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `banji` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
from flask import Flask, jsonify
from config import config
from api.quote_endpoints import quotes_bp
from web.routes import web_bp

# Create Flask app
app = Flask(__name__)
app.secret_key = config.secret_key

# Register blueprints
app.register_blueprint(quotes_bp, url_prefix='/api/quotes')
app.register_blueprint(web_bp)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version,
        'browser_mode': 'headless' if config.browser_headless else 'headed'
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
            'info': '/info',
            'quotes': '/api/quotes'
        },
        'capabilities': [
            'Refresh quote pricing via bulk edit',
            'Compare before/after pricing',
            'Screenshot capture on failures'
        ]
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


if __name__ == '__main__':
    mode = "headed" if not config.browser_headless else "headless"
    print("\n" + "="*50)
    print("🎭 Hi! I'm Banji")
    print("   Browser Automation for Buz")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   Browser mode: {mode}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
