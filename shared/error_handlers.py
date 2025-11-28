"""
Shared error handlers for Flask bots.

Usage:
    from shared.error_handlers import register_error_handlers
    register_error_handlers(app, logger)

This registers handlers for common HTTP errors. For API requests (Accept: application/json
or X-API-Key header), returns JSON. For browser requests, returns simple HTML.
"""

import logging
from flask import jsonify, request, render_template_string


# Simple HTML error template (no JS popups, just a div)
ERROR_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
               max-width: 600px; margin: 80px auto; padding: 20px; text-align: center; }
        .error-box { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
                     padding: 30px; margin: 20px 0; }
        h1 { color: #991b1b; margin: 0 0 10px 0; }
        p { color: #7f1d1d; margin: 0; }
        a { color: #2563eb; }
    </style>
</head>
<body>
    <div class="error-box">
        <h1>{{ code }} - {{ title }}</h1>
        <p>{{ message }}</p>
    </div>
    <p><a href="/">Return to home</a></p>
</body>
</html>
'''


def _wants_json():
    """Check if the request expects a JSON response."""
    # API requests (have API key header)
    if request.headers.get('X-API-Key'):
        return True
    # Explicit JSON accept header
    best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
    return best == 'application/json'


def _error_response(code, title, message):
    """Return appropriate error response based on request type."""
    if _wants_json():
        return jsonify({'error': message}), code
    return render_template_string(
        ERROR_TEMPLATE,
        code=code,
        title=title,
        message=message
    ), code


def register_error_handlers(app, logger=None):
    """
    Register standard error handlers on a Flask app.

    Args:
        app: Flask application instance
        logger: Optional logger instance. If not provided, uses module-level logger.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    @app.errorhandler(400)
    def bad_request(error):
        """Handle 400 Bad Request"""
        return _error_response(400, 'Bad Request', 'The request was invalid or malformed.')

    @app.errorhandler(401)
    def unauthorized(error):
        """Handle 401 Unauthorized"""
        return _error_response(401, 'Unauthorized', 'Authentication is required to access this resource.')

    @app.errorhandler(403)
    def forbidden(error):
        """Handle 403 Forbidden"""
        return _error_response(403, 'Forbidden', 'You do not have permission to access this resource.')

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 Not Found"""
        return _error_response(404, 'Not Found', 'The requested resource could not be found.')

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Handle 405 Method Not Allowed"""
        return _error_response(405, 'Method Not Allowed', f'The {request.method} method is not allowed for this endpoint.')

    @app.errorhandler(408)
    def request_timeout(error):
        """Handle 408 Request Timeout"""
        return _error_response(408, 'Request Timeout', 'The request took too long to process.')

    @app.errorhandler(429)
    def too_many_requests(error):
        """Handle 429 Too Many Requests"""
        return _error_response(429, 'Too Many Requests', 'Rate limit exceeded. Please try again later.')

    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 Internal Server Error"""
        logger.error(f"Internal server error: {error}", exc_info=True)
        return _error_response(500, 'Internal Server Error', 'An unexpected error occurred. Please try again later.')

    @app.errorhandler(502)
    def bad_gateway(error):
        """Handle 502 Bad Gateway"""
        logger.error(f"Bad gateway: {error}")
        return _error_response(502, 'Bad Gateway', 'The server received an invalid response from an upstream service.')

    @app.errorhandler(503)
    def service_unavailable(error):
        """Handle 503 Service Unavailable"""
        return _error_response(503, 'Service Unavailable', 'The service is temporarily unavailable. Please try again later.')

    @app.errorhandler(504)
    def gateway_timeout(error):
        """Handle 504 Gateway Timeout"""
        logger.warning(f"Gateway timeout: {error}")
        return _error_response(504, 'Gateway Timeout', 'The request timed out. Please try again.')
