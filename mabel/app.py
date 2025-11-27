"""Main Flask application for Mabel email bot."""

# Ensure project root (bot-team/) is on sys.path so `shared` imports work
from pathlib import Path
import sys
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
import time
from functools import wraps

from flask import Flask, jsonify, request, g
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config, ConfigError
from services.email_sender import EmailSender
from shared.auth import GatewayAuth
from shared.error_handlers import register_error_handlers


# Initialize Flask app
app = Flask(__name__)

# Global startup time for uptime tracking
app.config['START_TIME'] = time.time()


def init_app() -> Flask:
    """
    Initialize and configure the Flask application.

    Returns:
        Configured Flask app instance

    Raises:
        ConfigError: If configuration is invalid
    """
    # Load configuration
    try:
        config = Config()
        app.config['MABEL_CONFIG'] = config
    except ConfigError as e:
        raise ConfigError(f"Failed to load configuration: {e}") from e

    # Set Flask secret key
    app.secret_key = config.flask_secret_key

    # Trust proxy headers (nginx forwards X-Forwarded-Proto, X-Forwarded-Host, etc.)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize email sender
    email_sender = EmailSender(config)
    app.config['EMAIL_SENDER'] = email_sender

    # Initialize authentication via Chester's gateway
    auth = GatewayAuth(app, config)

    # Store auth instance in services.auth for backward compatibility with routes
    import services.auth as auth_module
    auth_module.auth = auth
    auth_module.login_required = auth.login_required
    auth_module.admin_required = auth.admin_required
    auth_module.get_current_user = auth.get_current_user

    # Register blueprints (import AFTER auth is initialized)
    from api.health import health_bp
    from api.email import email_bp
    from web.routes import web_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(email_bp, url_prefix='/api')
    app.register_blueprint(web_bp)

    # Register error handlers
    register_error_handlers(app, logging.getLogger(__name__))

    return app


def require_api_key(f):
    """
    Decorator to require API key authentication.

    Accepts either X-API-Key (standard) or X-Internal-Api-Key (legacy) header.
    Validates against BOT_API_KEY environment variable.

    Returns:
        401 JSON response if authentication fails
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = app.config['MABEL_CONFIG']
        # Accept both standard X-API-Key and legacy X-Internal-Api-Key
        api_key = request.headers.get('X-API-Key') or request.headers.get('X-Internal-Api-Key')

        if not api_key or api_key != config.internal_api_key:
            return jsonify({'error': 'unauthorized'}), 401

        return f(*args, **kwargs)

    return decorated_function


@app.before_request
def before_request():
    """Store request start time and correlation ID."""
    g.start_time = time.time()
    g.correlation_id = request.headers.get('X-Correlation-Id', 'none')


@app.after_request
def after_request(response):
    """Log request details after completion."""
    if hasattr(g, 'start_time'):
        duration_ms = (time.time() - g.start_time) * 1000
        logging.info(
            f"{request.method} {request.path} - "
            f"Status: {response.status_code} - "
            f"Duration: {duration_ms:.2f}ms - "
            f"Correlation-ID: {g.correlation_id}"
        )
    return response


@app.route('/info')
def info():
    """Bot information endpoint."""
    config = app.config['MABEL_CONFIG']
    return jsonify({
        'name': config.name,
        'description': config.description,
        'version': config.version,
        'emoji': config.emoji,
        'endpoints': {
            'api': {
                'POST /api/send-email': 'Send a single email',
                'POST /api/send-batch': 'Send multiple emails in batch'
            },
            'system': {
                '/health': 'Basic health check',
                '/health/deep': 'Deep health check with SMTP connection test',
                '/info': 'Bot information'
            }
        },
        'email_config': {
            'default_from': config.default_from,
            'default_sender_name': config.default_sender_name,
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'smtp_use_tls': config.smtp_use_tls
        }
    })


@app.route('/robots.txt')
def robots():
    """Robots.txt to prevent search engine indexing."""
    return '''User-agent: *
Disallow: /
''', 200, {'Content-Type': 'text/plain'}


# Initialize the app
init_app()


if __name__ == '__main__':
    """Run the Flask development server."""
    config = app.config['MABEL_CONFIG']
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=False
    )
