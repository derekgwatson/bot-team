import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Flask
from config import config
from web.routes import web_bp
from api.access import api_bp
from web.auth_routes import auth_bp
import os

app = Flask(__name__)

# Sessions / OAuth
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Auth (Google OAuth + Flask-Login)
init_auth(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/')
app.register_blueprint(web_bp, url_prefix='/')
app.register_blueprint(api_bp, url_prefix='/api')


@app.route('/robots.txt')
def robots():
    """Block search engine crawlers"""
    return """User-agent: *
Disallow: /
""", 200, {'Content-Type': 'text/plain'}


@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'service': 'rita'}, 200


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🧾 Hi! I'm Rita")
    print("   Access Helper")
    print(f"   Running on http://localhost:{config.server_port}")
    print("=" * 50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=True
    )
