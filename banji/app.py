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
from werkzeug.middleware.proxy_fix import ProxyFix
from config import config
from shared.auth import GatewayAuth
from shared.error_handlers import register_error_handlers
from services.session_manager import init_session_manager, get_session_manager
from services.job_processor import processor as job_processor
from database import db as job_db
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app with template folder
banji_dir = Path(__file__).parent
app = Flask(
    __name__,
    template_folder=str(banji_dir / 'web' / 'templates'),
    static_folder=str(banji_dir / 'web' / 'static')
)
app.secret_key = config.secret_key

# Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
# This ensures url_for generates https:// URLs when behind nginx with SSL
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize authentication via Chester's gateway
# MUST happen before importing blueprints that use @login_required
auth = GatewayAuth(app, config)

# Store auth instance in services.auth for backward compatibility with routes
import services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user

# Import blueprints AFTER auth is initialized (they use @login_required decorator)
from api.quote_endpoints import quotes_bp
from api.session_endpoints import sessions_bp
from web.routes import web_bp

# Initialize session manager
session_manager = init_session_manager(config, session_timeout_minutes=30)

# Start the background job processor
job_processor.start()
logger.info("Background job processor started")

# Register cleanup on shutdown
@atexit.register
def cleanup():
    """Cleanup sessions and job processor on shutdown."""
    try:
        job_processor.stop()
    except:
        pass
    try:
        get_session_manager().shutdown()
    except:
        pass

# Register blueprints
app.register_blueprint(quotes_bp, url_prefix='/api/quotes')
app.register_blueprint(sessions_bp, url_prefix='/api/sessions')
app.register_blueprint(web_bp)

# Register error handlers
register_error_handlers(app, logger)


@app.route('/api/orgs')
def list_orgs():
    """List available organizations for Buz operations."""
    # Combine configured orgs and those missing auth
    all_orgs = list(config.buz_orgs.keys()) + list(config.buz_orgs_missing_auth.keys())
    return jsonify({
        'orgs': sorted(all_orgs)
    })


@app.route('/health')
def health():
    """Health check endpoint."""
    job_stats = job_db.get_stats()
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version,
        'browser_mode': 'headless' if config.browser_headless else 'headed',
        'job_processor': 'running' if job_processor.is_running() else 'stopped',
        'jobs': {
            'pending': job_stats['pending'],
            'processing': job_stats['processing']
        }
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    active_sessions = session_manager.get_session_count()
    job_stats = job_db.get_stats()

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
                'GET /api/orgs': 'List available organizations',
                'POST /api/sessions/start': 'Start a new browser session',
                'DELETE /api/sessions/{session_id}': 'Close a browser session',
                'GET /api/sessions/{session_id}': 'Get session status',
                'POST /api/sessions/{session_id}/navigate/quote': 'Navigate to quote via Quick Lookup',
                'GET /api/sessions/{session_id}/quote/total': 'Extract quote total price',
                'POST /api/sessions/{session_id}/bulk-edit/open': 'Open bulk edit for quote',
                'POST /api/sessions/{session_id}/bulk-edit/save': 'Save bulk edit (triggers price recalc)',
                'GET /api/sessions/active': 'List all active sessions',
                'GET /api/sessions/health': 'Session endpoint health check',
                'POST /api/quotes/refresh-pricing': 'Refresh pricing for a single quote (sync)',
                'POST /api/quotes/batch-refresh-pricing': 'Refresh pricing for multiple quotes (sync, legacy)',
                'POST /api/quotes/batch-refresh-pricing-async': 'Queue batch refresh job (returns job_id)',
                'GET /api/quotes/jobs/{job_id}': 'Get job status and results',
                'GET /api/quotes/jobs': 'List recent jobs',
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
            'Screenshot capture on failures',
            'Async job queue for long-running batch operations'
        ],
        'session_info': {
            'active_sessions': active_sessions,
            'timeout_minutes': session_manager.session_timeout_minutes,
            'browser_mode': 'headless' if config.browser_headless else 'headed'
        },
        'job_queue': {
            'processor_running': job_processor.is_running(),
            'pending_jobs': job_stats['pending'],
            'processing_jobs': job_stats['processing']
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
