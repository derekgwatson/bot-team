from flask import Flask, jsonify
from config import config
from api.contacts import api_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth
from database.migrations import auto_migrate
import os

app = Flask(__name__)

# Configure Flask for sessions and OAuth
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

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
        'endpoints': {
            'web': '/',
            'api': '/api',
            'health': '/health'
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("👔 Hi! I'm Peter")
    print("   Staff Directory")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    # Run auto-migration on startup
    auto_migrate()

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=True
    )
