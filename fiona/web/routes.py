"""
Web Routes for Fiona
Provides UI for viewing and editing fabric descriptions
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from database.db import db
from services.mavis_service import mavis_service
from services.auth import login_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/')
@login_required
def index():
    """Display Fiona main page - fabric description list"""
    # Get query parameters
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get fabrics
    if search_query:
        fabrics = db.search_fabrics(query=search_query, limit=per_page * page)
        # Simple pagination for search results
        fabrics = fabrics[(page - 1) * per_page:page * per_page]
    else:
        fabrics = db.get_all_fabrics(limit=per_page, offset=(page - 1) * per_page)

    total = db.get_fabric_count()
    total_pages = (total + per_page - 1) // per_page

    # Check Mavis connection
    mavis_status = mavis_service.check_connection()

    return render_template(
        'index.html',
        config=config,
        fabrics=fabrics,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        search_query=search_query,
        mavis_status=mavis_status,
        current_user=current_user
    )


@web_bp.route('/fabric/<code>')
@login_required
def view_fabric(code):
    """View/edit a single fabric description"""
    fabric = db.get_fabric_by_code(code)

    # Get product data from Mavis
    mavis_product = mavis_service.get_product(code)

    return render_template(
        'fabric.html',
        config=config,
        fabric=fabric,
        product_code=code.upper(),
        mavis_product=mavis_product,
        current_user=current_user
    )


@web_bp.route('/fabric/<code>/save', methods=['POST'])
@login_required
def save_fabric(code):
    """Save fabric description from form"""
    try:
        fabric_data = {
            'product_code': code,
            'supplier_material': request.form.get('supplier_material', '').strip() or None,
            'supplier_material_type': request.form.get('supplier_material_type', '').strip() or None,
            'supplier_colour': request.form.get('supplier_colour', '').strip() or None,
            'watson_material': request.form.get('watson_material', '').strip() or None,
            'watson_colour': request.form.get('watson_colour', '').strip() or None,
        }

        db.upsert_fabric(fabric_data, updated_by=current_user.email)

        # Redirect back to fabric page with success message
        return redirect(url_for('web.view_fabric', code=code, saved=1))

    except Exception as e:
        return render_template(
            'fabric.html',
            config=config,
            fabric=db.get_fabric_by_code(code),
            product_code=code.upper(),
            mavis_product=mavis_service.get_product(code),
            current_user=current_user,
            error=str(e)
        )


@web_bp.route('/fabric/<code>/delete', methods=['POST'])
@login_required
def delete_fabric(code):
    """Delete a fabric description"""
    db.delete_fabric(code)
    return redirect(url_for('web.index', deleted=code))


@web_bp.route('/new')
@login_required
def new_fabric():
    """Create a new fabric description - lookup product in Mavis first"""
    return render_template(
        'new_fabric.html',
        config=config,
        current_user=current_user
    )


@web_bp.route('/lookup', methods=['POST'])
@login_required
def lookup_product():
    """Lookup a product code in Mavis"""
    code = request.form.get('product_code', '').strip().upper()

    if not code:
        return redirect(url_for('web.new_fabric', error='Product code is required'))

    # Check if we already have this fabric
    existing = db.get_fabric_by_code(code)
    if existing:
        return redirect(url_for('web.view_fabric', code=code))

    # Check Mavis for the product
    mavis_product = mavis_service.get_product(code)

    return render_template(
        'new_fabric.html',
        config=config,
        current_user=current_user,
        product_code=code,
        mavis_product=mavis_product
    )
