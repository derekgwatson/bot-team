from flask import Flask, jsonify
from config import config
from api.deployments import api_bp
from web.routes import web_bp

app = Flask(__name__)

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
        'sally_url': config.sally_url,
        'endpoints': {
            'web': '/',
            'api': '/api',
            'health': '/health'
        }
    })

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 Hi! I'm Dorothy")
    print("   Deployment Orchestrator")
    print(f"   Running on http://localhost:{config.server_port}")
    print(f"   Using Sally at {config.sally_url}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=True
    )
