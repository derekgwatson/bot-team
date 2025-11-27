"""Web routes for Doc dashboard"""

from flask import Blueprint, render_template
from database.db import db
from services.checkup import checkup_service
from services.sync import sync_service
from services.test_runner import test_runner
from services.auth import admin_required

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@admin_required
def dashboard():
    """Main dashboard showing team health"""
    # Get bot statuses
    statuses = checkup_service.get_latest_status()

    # Get sync status
    sync_status = sync_service.get_sync_status()

    # Get latest test run
    latest_test = test_runner.get_latest_run()

    # Get team vitals
    vitals = checkup_service.get_vitals(hours=24)

    return render_template(
        'dashboard.html',
        statuses=statuses,
        sync_status=sync_status,
        latest_test=latest_test,
        vitals=vitals
    )
