"""Banji - Playwright Browser Automation for Buz."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `banji` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import atexit
from flask import Flask, jsonify
from config import config
from api.quote_endpoints import quotes_bp
from api.session_endpoints import sessions_bp
from web.routes import web_bp
from web.auth_routes import auth_bp
from services.auth import init_auth
from services.session_manager import init_session_manager, get_session_manager

# Create Flask app with template folder
banji_dir = Path(__file__).parent
app = Flask(
    __name__,
    template_folder=str(banji_dir / 'web' / 'templates'),
    static_folder=str(banji_dir / 'web' / 'static')
)
app.secret_key = config.secret_key

# Initialize authentication
init_auth(app)

# Initialize session manager
session_manager = init_session_manager(config, session_timeout_minutes=30)

# Register cleanup on shutdown
@atexit.register
def cleanup():
    """Cleanup sessions on shutdown."""
    try:
        get_session_manager().shutdown()
    except:
        pass

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/')
app.register_blueprint(quotes_bp, url_prefix='/api/quotes')
app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
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
    active_sessions = session_manager.get_session_count()

    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '🎭',
        'endpoints': {
            'web': {
                '/': 'Home page with session management UI'
            },
            'api': {
                'POST /api/sessions/start': 'Start a new browser session',
                'DELETE /api/sessions/{session_id}': 'Close a browser session',
                'GET /api/sessions/{session_id}': 'Get session status',
                'POST /api/sessions/{session_id}/navigate/quote': 'Navigate to quote via Quick Lookup',
                'GET /api/sessions/{session_id}/quote/total': 'Extract quote total price',
                'POST /api/sessions/{session_id}/bulk-edit/open': 'Open bulk edit for quote',
                'POST /api/sessions/{session_id}/bulk-edit/save': 'Save bulk edit (triggers price recalc)',
                'GET /api/sessions/active': 'List all active sessions',
                'GET /api/sessions/health': 'Session endpoint health check',
                'POST /api/quotes/refresh-pricing': 'Refresh pricing for a single quote',
                'POST /api/quotes/batch-refresh-pricing': 'Refresh pricing for multiple quotes in one session',
                'GET /api/quotes/health': 'Quotes endpoint health check'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        },
        'capabilities': [
            'Session-based browser automation',
            'Navigate to quotes via Quick Lookup',
            'Extract quote total prices',
            'Open and save bulk edit (trigger price recalc)',
            'Maintain browser state across multiple API calls',
            'Multi-organization support',
            'Screenshot capture on failures'
        ],
        'session_info': {
            'active_sessions': active_sessions,
            'timeout_minutes': session_manager.session_timeout_minutes,
            'browser_mode': 'headless' if config.browser_headless else 'headed'
        }
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
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        threaded=False,  # Playwright sync API is not thread-safe
        use_reloader=False  # Prevent reloader from causing threading issues
    )
