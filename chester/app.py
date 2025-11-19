"""Chester - Bot Team Concierge."""
import os
from flask import Flask, jsonify
from chester.config import config
from chester.api.bots import bots_bp
from chester.api.deployment import deployment_bp
from chester.web.routes import web_bp

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
