from flask import Flask, jsonify
from config import config
from api.contacts import api_bp
from web.routes import web_bp
import os
import sys

app = Flask(__name__)

# Session configuration
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# Initialize Google OAuth
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.auth.google_oauth import GoogleOAuth

oauth = GoogleOAuth(app, config)

# Register blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp, url_prefix='/')

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
    print("📱 Hi! I'm Peter")
    print("   Phone Directory Manager")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=True
    )
