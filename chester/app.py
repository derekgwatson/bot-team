"""Chester - Bot Team Concierge."""
import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from config import config
from api.bots import bots_bp
from web.routes import web_bp

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Register blueprints
app.register_blueprint(bots_bp, url_prefix='/api')
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
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
