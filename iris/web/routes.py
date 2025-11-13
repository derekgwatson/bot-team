from flask import Blueprint, render_template, request
from services.google_reports import reports_service
from datetime import datetime, timedelta

web_bp = Blueprint('web', __name__, template_folder='templates')

@web_bp.route('/')
def index():
    """Home page showing storage usage overview"""
    # Get usage data for yesterday (most recent available)
    usage_data = reports_service.get_user_usage()

    if isinstance(usage_data, dict) and 'error' in usage_data:
        error = usage_data['error']
        usage_data = []
    else:
        error = None
        # Sort by total usage descending
        usage_data = sorted(usage_data, key=lambda x: x.get('total_used_gb', 0), reverse=True)

    return render_template('index.html', usage=usage_data, error=error)

@web_bp.route('/user/<email>')
def user_detail(email):
    """User detail page showing individual usage"""
    usage_data = reports_service.get_user_usage(email=email)

    if isinstance(usage_data, dict) and 'error' in usage_data:
        error = usage_data['error']
        usage = None
    elif len(usage_data) == 0:
        error = 'No usage data found for this user'
        usage = None
    else:
        error = None
        usage = usage_data[0]

    return render_template('user_detail.html', usage=usage, email=email, error=error)
