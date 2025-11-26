"""
Travis Web Routes
Serves the welcome page and staff management interface
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from flask import Blueprint, render_template
from flask_login import current_user
import logging

from travis.config import config
from travis.database.db import db
from travis.services.auth import login_required

logger = logging.getLogger(__name__)

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Welcome page"""
    return render_template('index.html', config=config, current_user=current_user)


@web_bp.route('/staff')
@login_required
def staff_list():
    """Staff listing page"""
    staff = db.get_all_staff()
    # Remove device tokens for display
    for s in staff:
        s.pop('device_token', None)
    return render_template('staff.html', config=config, staff=staff, current_user=current_user)
