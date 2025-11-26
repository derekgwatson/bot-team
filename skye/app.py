"""Skye - Scheduler Bot for the bot team."""
import sys
from pathlib import Path

# Ensure project root (bot-team/) is on sys.path so `shared` and `skye` imports work
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import os
import atexit
from datetime import datetime, timezone
from flask import Flask, jsonify
from config import config
from shared.auth import GatewayAuth
from services.scheduler import scheduler_service
from api.routes import api_bp
from web.routes import web_bp

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize authentication via Chester's gateway
auth = GatewayAuth(app, config)

# Store auth instance in services.auth for backward compatibility with routes
import services.auth as auth_module
auth_module.auth = auth
auth_module.login_required = auth.login_required
auth_module.admin_required = auth.admin_required
auth_module.get_current_user = auth.get_current_user



def relative_time(timestamp: str) -> str:
    """
    Convert ISO timestamp to human-readable relative time.
    Returns: "Just now", "X minutes ago", "in X minutes", etc.
    """
    if not timestamp:
        return "Never"

    try:
        # Parse ISO timestamp (handle various formats)
        ts = timestamp.replace('Z', '+00:00')
        if '+' not in ts and len(ts) == 19:
            # No timezone info, assume UTC
            dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(ts)

        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = diff.total_seconds()

        # Future time (negative seconds)
        if seconds < 0:
            seconds = abs(seconds)
            if seconds < 60:
                return "in a moment"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"in {minutes} minute{'s' if minutes != 1 else ''}"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"in {hours} hour{'s' if hours != 1 else ''}"
            else:
                days = int(seconds / 86400)
                return f"in {days} day{'s' if days != 1 else ''}"

        # Past time
        if seconds < 60:
            return "Just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    except (ValueError, TypeError):
        return timestamp[:19] if len(str(timestamp)) >= 19 else str(timestamp)


# Register Jinja2 filter
app.jinja_env.filters['relative_time'] = relative_time



# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(web_bp)


@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'bot': config.name,
        'version': config.version,
        'scheduler_running': scheduler_service.is_running()
    })


@app.route('/info')
def info():
    """Bot information endpoint."""
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'personality': config.personality,
        'emoji': '\u23f0',
        'endpoints': {
            'web': {
                '/': 'Dashboard with scheduler overview',
                '/jobs': 'List all scheduled jobs',
                '/jobs/<job_id>': 'View job details and history',
                '/jobs/new': 'Create new job (admin)',
                '/history': 'View execution history',
                '/failures': 'View recent failures'
            },
            'api': {
                'GET /api/jobs': 'List all jobs',
                'GET /api/jobs/<job_id>': 'Get job details',
                'POST /api/jobs': 'Create new job',
                'PUT /api/jobs/<job_id>': 'Update job',
                'DELETE /api/jobs/<job_id>': 'Delete job',
                'POST /api/jobs/<job_id>/run': 'Run job immediately',
                'POST /api/jobs/<job_id>/enable': 'Enable job',
                'POST /api/jobs/<job_id>/disable': 'Disable job',
                'GET /api/jobs/<job_id>/history': 'Get job execution history',
                'GET /api/executions': 'Get recent executions',
                'GET /api/executions/failed': 'Get failed executions',
                'GET /api/stats': 'Get scheduler statistics',
                'GET /api/scheduler/status': 'Get scheduler status'
            },
            'system': {
                '/health': 'Health check',
                '/info': 'Bot information'
            }
        }
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


# Start scheduler on app startup (for both dev and gunicorn)
def start_scheduler():
    """Start the scheduler if not already running."""
    if not scheduler_service.is_running():
        scheduler_service.start()
        print(f"\u23f0 Skye: Scheduler started with {len(scheduler_service.get_scheduled_jobs())} jobs")


def stop_scheduler():
    """Stop the scheduler on app shutdown."""
    if scheduler_service.is_running():
        scheduler_service.stop()
        print("\u23f0 Skye: Scheduler stopped")


# Register shutdown handler
atexit.register(stop_scheduler)

# Start scheduler (runs on import for gunicorn, or when running directly)
start_scheduler()


if __name__ == '__main__':
    print("\n" + "="*50)
    print("\u23f0 Hi! I'm Skye")
    print("   Scheduler Bot - keeping everything on time")
    print(f"   Running on http://localhost:{config.server_port}")
    print("="*50 + "\n")

    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    )
