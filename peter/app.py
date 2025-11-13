from flask import Flask, jsonify, render_template
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
from shared.auth.google_oauth import GoogleAuth

oauth = GoogleAuth(app, config)

# Auth routes
@app.route('/login')
def login():
    """Login page"""
    return render_template('auth/login.html',
                         bot_name='Peter',
                         bot_icon='📱',
                         bot_description='Phone Directory Manager',
                         primary_color='#3498db',
                         secondary_color='#2980b9')

@app.route('/auth/login')
def auth_login():
    """Start OAuth flow"""
    return oauth.login_route()

@app.route('/auth/callback')
def auth_callback():
    """OAuth callback"""
    return oauth.callback_route()

@app.route('/auth/logout')
def auth_logout():
    """Logout"""
    return oauth.logout_route()

@app.route('/access-denied')
def access_denied():
    """Access denied page"""
    return render_template('auth/access_denied.html',
                         bot_name='Peter',
                         message='You need authorized access to view the phone directory.')

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
