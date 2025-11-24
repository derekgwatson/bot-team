"""
Web Routes for Mavis
Simple status page showing sync status and product statistics
"""

import threading
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import current_user
from database.db import db
from services.sync_service import sync_service
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Display Mavis status page (staff only)"""
    # Get sync status
    sync_status = sync_service.get_status()

    # Get product stats
    product_count = db.get_product_count()

    # Get recent sync history
    sync_history = sync_service.get_sync_history(limit=5)

    # Check for flash messages from sync trigger
    sync_triggered = request.args.get('sync_triggered')
    sync_error = request.args.get('sync_error')

    return render_template(
        'index.html',
        config=config,
        sync_status=sync_status,
        product_count=product_count,
        sync_history=sync_history,
        sync_triggered=sync_triggered,
        sync_error=sync_error,
        current_user=current_user
    )


@web_bp.route('/sync/trigger', methods=['POST'])
@login_required
def trigger_sync():
    """Trigger a manual sync from Unleashed"""
    # Check if a sync is already running
    if db.is_sync_running('products'):
        return redirect(url_for('web.index', sync_error='A sync is already running'))

    # Run sync in background thread so we don't block the UI
    def run_sync():
        try:
            sync_service.run_product_sync()
        except Exception:
            # Error will be captured in sync metadata
            pass

    thread = threading.Thread(target=run_sync)
    thread.daemon = True
    thread.start()

    return redirect(url_for('web.index', sync_triggered='1'))


@web_bp.route('/products')
@login_required
def products():
    """Product search page"""
    query = request.args.get('q', '').strip()
    code = request.args.get('code', '').strip()

    product = None
    results = []

    # If exact code requested, look it up
    if code:
        product = db.get_product_by_code(code)
        # Add valid fabric flag
        if product:
            sub_group = (product.get('product_sub_group') or '').lower()
            is_valid = (
                product.get('product_group', '').lower().startswith('fabric')
                and not product.get('is_obsolete')
                and product.get('is_sellable')
                and sub_group != 'ignore'
            )
            product['is_valid_fabric'] = is_valid
    # Otherwise search
    elif query:
        results = db.search_products(query)

    # Get fabric stats
    fabric_count = len(db.get_valid_fabric_codes())

    return render_template(
        'products.html',
        config=config,
        query=query,
        code=code,
        product=product,
        results=results,
        fabric_count=fabric_count,
        current_user=current_user
    )
