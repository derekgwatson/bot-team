"""
Web Routes for Fiona

Public routes (all staff):
- / - Read-only fabric directory with instant search

Admin routes (admins only):
- /admin - Admin dashboard with editing capabilities
- /admin/fabric/<code> - Edit fabric description
- /admin/import - Import from Google Sheets
"""

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, make_response
from flask_login import current_user
from database.db import db
from services.mavis_service import mavis_service
from services.sheets_import import sheets_import_service
from services.fabric_sync import fabric_sync_service
from services.auth import login_required, admin_required
from config import config

web_bp = Blueprint('web', __name__, template_folder='templates')


# ─────────────────────────────────────────────────────────────────────────────
# Public Routes (All Staff)
# ─────────────────────────────────────────────────────────────────────────────

@web_bp.route('/')
@login_required
def index():
    """Route to user's preferred view based on saved preference"""
    # Admins default to admin view
    if current_user.is_admin:
        preference = request.cookies.get('fiona_view', 'admin')
    else:
        preference = request.cookies.get('fiona_view', '')

    # Redirect based on preference
    if preference == 'admin' and current_user.is_admin:
        return redirect(url_for('web.admin_index'))
    elif preference == 'all':
        return redirect(url_for('web.all_fabrics'))
    elif preference == 'rebadged':
        return redirect(url_for('web.rebadged_page'))
    else:
        # No preference set - show landing page
        return redirect(url_for('web.choose_view'))


@web_bp.route('/choose')
@login_required
def choose_view():
    """Landing page to choose view preference"""
    return render_template(
        'choose.html',
        config=config,
        current_user=current_user
    )


@web_bp.route('/set-view/<view>')
@login_required
def set_view(view):
    """Set the user's view preference and redirect there"""
    valid_views = ['all', 'rebadged']
    if current_user.is_admin:
        valid_views.append('admin')

    if view not in valid_views:
        view = 'all'

    # Redirect to the chosen view
    if view == 'admin':
        response = make_response(redirect(url_for('web.admin_index')))
    elif view == 'rebadged':
        response = make_response(redirect(url_for('web.rebadged_page')))
    else:
        response = make_response(redirect(url_for('web.all_fabrics')))

    # Save preference in cookie (expires in 1 year)
    response.set_cookie('fiona_view', view, max_age=365*24*60*60, samesite='Lax')
    return response


@web_bp.route('/all')
@login_required
def all_fabrics():
    """Display read-only fabric directory with instant search (all staff)"""
    # Get all fabrics for instant search
    fabrics = db.get_all_fabrics(limit=5000)  # Load all for client-side search
    total = db.get_fabric_count()

    # Check Mavis connection
    mavis_status = mavis_service.check_connection()

    # Get distinct fabric types for the filter dropdown
    fabric_types = fabric_sync_service.get_fabric_types()

    return render_template(
        'index.html',
        config=config,
        fabrics=fabrics,
        total=total,
        mavis_status=mavis_status,
        fabric_types=fabric_types,
        current_user=current_user
    )


# ─────────────────────────────────────────────────────────────────────────────
# Admin Routes (Admins Only)
# ─────────────────────────────────────────────────────────────────────────────

@web_bp.route('/admin')
@admin_required
def admin_index():
    """Admin dashboard with editing capabilities"""
    # Get query parameters for pagination
    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Get fabrics with pagination
    if search_query:
        fabrics = db.search_fabrics(query=search_query, limit=per_page * page)
        fabrics = fabrics[(page - 1) * per_page:page * per_page]
    else:
        fabrics = db.get_all_fabrics(limit=per_page, offset=(page - 1) * per_page)

    total = db.get_fabric_count()
    total_pages = (total + per_page - 1) // per_page

    # Check services status
    mavis_status = mavis_service.check_connection()
    sheets_status = sheets_import_service.is_available()

    return render_template(
        'admin/index.html',
        config=config,
        fabrics=fabrics,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        search_query=search_query,
        mavis_status=mavis_status,
        sheets_status=sheets_status,
        current_user=current_user
    )


@web_bp.route('/admin/fabric/<code>')
@admin_required
def edit_fabric(code):
    """Edit a fabric description (admin only)"""
    fabric = db.get_fabric_by_code(code)
    mavis_product = mavis_service.get_product(code)

    return render_template(
        'admin/fabric.html',
        config=config,
        fabric=fabric,
        product_code=code.upper(),
        mavis_product=mavis_product,
        current_user=current_user
    )


@web_bp.route('/admin/fabric/<code>/save', methods=['POST'])
@admin_required
def save_fabric(code):
    """Save fabric description (admin only)"""
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

        return redirect(url_for('web.edit_fabric', code=code, saved=1))

    except Exception as e:
        return render_template(
            'admin/fabric.html',
            config=config,
            fabric=db.get_fabric_by_code(code),
            product_code=code.upper(),
            mavis_product=mavis_service.get_product(code),
            current_user=current_user,
            error=str(e)
        )


@web_bp.route('/admin/fabric/<code>/delete', methods=['POST'])
@admin_required
def delete_fabric(code):
    """Delete a fabric description (admin only)"""
    db.delete_fabric(code)
    return redirect(url_for('web.admin_index', deleted=code))


@web_bp.route('/admin/new')
@admin_required
def new_fabric():
    """Create a new fabric description (admin only)"""
    return render_template(
        'admin/new_fabric.html',
        config=config,
        current_user=current_user
    )


@web_bp.route('/admin/lookup', methods=['POST'])
@admin_required
def lookup_product():
    """Lookup a product code in Mavis (admin only)"""
    code = request.form.get('product_code', '').strip().upper()

    if not code:
        return redirect(url_for('web.new_fabric', error='Product code is required'))

    # Check if we already have this fabric
    existing = db.get_fabric_by_code(code)
    if existing:
        return redirect(url_for('web.edit_fabric', code=code))

    # Check Mavis for the product
    mavis_product = mavis_service.get_product(code)

    return render_template(
        'admin/new_fabric.html',
        config=config,
        current_user=current_user,
        product_code=code,
        mavis_product=mavis_product
    )


@web_bp.route('/admin/import')
@admin_required
def import_page():
    """Google Sheets import page (admin only)"""
    sheets_status = sheets_import_service.is_available()

    return render_template(
        'admin/import.html',
        config=config,
        sheets_status=sheets_status,
        current_user=current_user
    )


@web_bp.route('/admin/import/preview', methods=['POST'])
@admin_required
def import_preview():
    """Preview import from Google Sheets (admin only)"""
    result = sheets_import_service.run_import(
        updated_by=current_user.email,
        dry_run=True
    )

    sheets_status = sheets_import_service.is_available()

    return render_template(
        'admin/import.html',
        config=config,
        sheets_status=sheets_status,
        preview_result=result,
        current_user=current_user
    )


@web_bp.route('/admin/import/run', methods=['POST'])
@admin_required
def import_run():
    """Run import from Google Sheets (admin only)"""
    result = sheets_import_service.run_import(
        updated_by=current_user.email,
        dry_run=False
    )

    sheets_status = sheets_import_service.is_available()

    return render_template(
        'admin/import.html',
        config=config,
        sheets_status=sheets_status,
        import_result=result,
        current_user=current_user
    )


# ─────────────────────────────────────────────────────────────────────────────
# Sync Routes (Admin Only)
# ─────────────────────────────────────────────────────────────────────────────

@web_bp.route('/admin/sync')
@admin_required
def sync_page():
    """Sync status page - compare Fiona with Mavis (admin only)"""
    comparison = fabric_sync_service.compare_with_mavis()

    return render_template(
        'admin/sync.html',
        config=config,
        comparison=comparison,
        current_user=current_user
    )


@web_bp.route('/admin/sync/add-missing', methods=['POST'])
@admin_required
def sync_add_missing():
    """Add missing fabrics from Mavis to Fiona (admin only)"""
    result = fabric_sync_service.add_missing_fabrics(updated_by=current_user.email)

    comparison = fabric_sync_service.compare_with_mavis()

    return render_template(
        'admin/sync.html',
        config=config,
        comparison=comparison,
        add_result=result,
        current_user=current_user
    )


@web_bp.route('/admin/sync/delete', methods=['POST'])
@admin_required
def sync_delete_flagged():
    """Delete selected fabrics flagged for deletion (admin only)"""
    codes_to_delete = request.form.getlist('codes')

    if not codes_to_delete:
        comparison = fabric_sync_service.compare_with_mavis()
        return render_template(
            'admin/sync.html',
            config=config,
            comparison=comparison,
            delete_error='No fabrics selected for deletion',
            current_user=current_user
        )

    result = fabric_sync_service.delete_flagged_fabrics(codes_to_delete)

    comparison = fabric_sync_service.compare_with_mavis()

    return render_template(
        'admin/sync.html',
        config=config,
        comparison=comparison,
        delete_result=result,
        current_user=current_user
    )


@web_bp.route('/admin/incomplete')
@admin_required
def incomplete_page():
    """View fabrics missing supplier description fields (admin only)"""
    incomplete_fabrics = fabric_sync_service.get_incomplete_fabrics()

    return render_template(
        'admin/incomplete.html',
        config=config,
        fabrics=incomplete_fabrics,
        total=len(incomplete_fabrics),
        current_user=current_user
    )


@web_bp.route('/rebadged')
@login_required
def rebadged_page():
    """View fabrics with Watson names different from supplier names (staff)"""
    rebadged_fabrics = fabric_sync_service.get_rebadged_fabrics()

    # Get distinct fabric types for the filter dropdown
    fabric_types = fabric_sync_service.get_fabric_types()

    return render_template(
        'rebadged.html',
        config=config,
        fabrics=rebadged_fabrics,
        total=len(rebadged_fabrics),
        fabric_types=fabric_types,
        current_user=current_user
    )
