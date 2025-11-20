"""Main Flask application for Mabel email bot."""

import logging
import time
from functools import wraps

from flask import Flask, jsonify, request, g

from config import Config, ConfigError
from services.email_sender import EmailSender


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

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize email sender
    email_sender = EmailSender(config)
    app.config['EMAIL_SENDER'] = email_sender

    # Register blueprints
    from api.health import health_bp
    from api.email import email_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(email_bp, url_prefix='/api')

    return app


def require_api_key(f):
    """
    Decorator to require API key authentication.

    Checks for X-Internal-Api-Key header and validates against config.

    Returns:
        401 JSON response if authentication fails
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = app.config['MABEL_CONFIG']
        api_key = request.headers.get('X-Internal-Api-Key')

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


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': 'not_found', 'message': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logging.error(f"Internal server error: {error}")
    return jsonify({'error': 'internal_error', 'message': 'Internal server error'}), 500


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
