import sys
import os
# Add shared modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, jsonify, render_template
from config import config
from api.routes import api_bp
from web.routes import web_bp
from shared.auth.google_oauth import GoogleAuth

app = Flask(__name__)

# Initialize authentication
auth = GoogleAuth(app, config)

# Auth routes
@app.route('/login')
def login():
    """Login page"""
    return render_template('auth/login.html',
                         bot_name='Pam',
                         bot_icon='📞',
                         bot_description='Your Friendly Phone Directory',
                         primary_color='#1abc9c',
                         secondary_color='#16a085')

@app.route('/auth/login')
def auth_login():
    """Start OAuth flow"""
    return auth.login_route()

@app.route('/auth/callback')
def auth_callback():
    """OAuth callback"""
    return auth.callback_route()

@app.route('/auth/logout')
def auth_logout():
    """Logout"""
    return auth.logout_route()

@app.route('/access-denied')
def access_denied():
    """Access denied page"""
    return render_template('auth/access_denied.html',
                         bot_name='Pam',
                         message='You need a Watson Blinds email address to access the phone directory.')

# Register blueprints
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
    print("📞 Hi! I'm Pam")
    print("   Your Friendly Phone Directory")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=True
    )
