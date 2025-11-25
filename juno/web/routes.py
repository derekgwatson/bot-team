"""
Juno Web Routes
Serves customer-facing tracking pages
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, render_template, jsonify
import logging

from juno.config import config
from juno.database.db import db

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__)


@web_bp.route('/')
def index():
    """Welcome page"""
    return render_template('index.html', config=config)


@web_bp.route('/links')
def links():
    """Active tracking links page"""
    active_links = db.get_all_active_links()
    return render_template('links.html', config=config, links=active_links)


@web_bp.route('/track/<code>')
def track(code: str):
    """
    Customer-facing tracking page.
    Shows a map with the staff member's location (when in transit).
    """
    # Get the tracking link
    link = db.get_tracking_link_by_code(code)

    if not link:
        return render_template(
            'error.html',
            title='Link Not Found',
            message='This tracking link is not valid or has expired.'
        ), 404

    # Check if expired
    if link['status'] == 'expired':
        return render_template(
            'error.html',
            title='Link Expired',
            message='This tracking link has expired.'
        )

    # Check if cancelled
    if link['status'] == 'cancelled':
        return render_template(
            'error.html',
            title='Tracking Cancelled',
            message='This tracking session has been cancelled.'
        )

    # Check if arrived
    if link['status'] == 'arrived':
        return render_template(
            'arrived.html',
            link=link,
            customer_name=link.get('customer_name', 'there')
        )

    # Record the view
    db.record_view(code)

    # Active link - show tracking page
    return render_template(
        'tracking.html',
        link=link,
        code=code,
        customer_name=link.get('customer_name', 'there'),
        destination_address=link.get('destination_address', ''),
        destination_lat=link.get('destination_lat') or config.default_lat,
        destination_lng=link.get('destination_lng') or config.default_lng,
        default_zoom=config.default_zoom,
        poll_interval=config.poll_interval * 1000,  # Convert to milliseconds
        google_maps_api_key=config.google_maps_api_key or ''
    )
