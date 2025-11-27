"""
Shared error handlers for Flask bots.

Usage:
    from shared.error_handlers import register_error_handlers
    register_error_handlers(app, logger)
"""

import logging
from flask import jsonify


def register_error_handlers(app, logger=None):
    """
    Register standard error handlers on a Flask app.

    Args:
        app: Flask application instance
        logger: Optional logger instance. If not provided, uses module-level logger.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        """Handle internal server errors"""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500
