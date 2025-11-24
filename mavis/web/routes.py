"""
Web Routes for Mavis
Simple status page showing sync status and product statistics
"""

from flask import Blueprint, render_template
from database.db import db
from services.sync_service import sync_service
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
def index():
    """Display Mavis status page"""
    # Get sync status
    sync_status = sync_service.get_status()

    # Get product stats
    product_count = db.get_product_count()

    # Get recent sync history
    sync_history = sync_service.get_sync_history(limit=5)

    return render_template(
        'index.html',
        config=config,
        sync_status=sync_status,
        product_count=product_count,
        sync_history=sync_history
    )
