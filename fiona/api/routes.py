"""
API Routes for Fiona

REST API for fabric description management:
- Get/set fabric descriptions
- Bulk operations
- Mavis integration
"""

from flask import Blueprint, jsonify, request
import logging

from database.db import db
from services.mavis_service import mavis_service
from services.fabric_sync import fabric_sync_service
from shared.auth.bot_api import api_key_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Bot Introduction
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """Return Fiona's introduction"""
    return jsonify({
        'name': 'Fiona',
        'role': 'Fabric Description Manager',
        'description': (
            'I manage friendly names for Unleashed fabric products. '
            'For each fabric, I store both the original supplier names '
            '(material, material type, colour) and optional Watson re-badged names. '
            'Use me when you need human-friendly fabric descriptions.'
        ),
        'capabilities': [
            'Store friendly names for fabric products',
            'Lookup fabric descriptions by product code',
            'Bulk fabric description operations',
            'Integration with Mavis for product validation',
            'Search fabrics by material or colour'
        ],
        'endpoints': {
            'GET /api/fabrics': 'Get a fabric description by code (?code=XXX)',
            'POST /api/fabrics': 'Create or update a fabric description',
            'DELETE /api/fabrics': 'Delete a fabric description',
            'POST /api/fabrics/bulk': 'Bulk lookup or upsert fabrics',
            'GET /api/fabrics/search': 'Search fabrics (?q=XXX)',
            'GET /api/fabrics/stats': 'Get fabric description statistics',
            'GET /api/mavis/status': 'Check Mavis connection status'
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# Fabric Description Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def format_fabric_response(fabric: dict) -> dict:
    """Format a fabric record for API response"""
    return {
        'product_code': fabric['product_code'],
        'supplier_material': fabric['supplier_material'],
        'supplier_material_type': fabric['supplier_material_type'],
        'supplier_colour': fabric['supplier_colour'],
        'watson_material': fabric['watson_material'],
        'watson_colour': fabric['watson_colour'],
        'fabric_type': fabric.get('fabric_type'),
        'price_category': fabric.get('price_category'),
        'width': fabric.get('width'),
        'updated_at': fabric['updated_at'],
        'updated_by': fabric['updated_by']
    }


@api_bp.route('/fabrics', methods=['GET'])
@api_key_required
def get_fabric():
    """
    Get a fabric description by product code.

    Query parameters:
        code (required): Product code (case-insensitive)
        include_mavis (optional): Include Mavis product data if true
    """
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': "Missing required parameter 'code'"}), 400

        fabric = db.get_fabric_by_code(code)

        # Optionally include Mavis product data
        include_mavis = request.args.get('include_mavis', '').lower() == 'true'
        mavis_data = None
        if include_mavis:
            mavis_data = mavis_service.get_product(code)

        if not fabric:
            # No fabric description exists
            if mavis_data:
                # But product exists in Mavis
                return jsonify({
                    'found': False,
                    'product_code': code.strip().upper(),
                    'message': 'No fabric description exists for this product',
                    'mavis_product': mavis_data
                }), 404
            else:
                return jsonify({
                    'error': f"Fabric not found: {code.strip().upper()}"
                }), 404

        response = format_fabric_response(fabric)
        if mavis_data:
            response['mavis_product'] = mavis_data

        return jsonify(response)

    except Exception as e:
        logger.exception(f"Error getting fabric {request.args.get('code')}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics', methods=['POST'])
@api_key_required
def upsert_fabric():
    """
    Create or update a fabric description.

    Request body:
        {
            "product_code": "FAB001",
            "supplier_material": "Blockout",
            "supplier_material_type": "Roller Blind",
            "supplier_colour": "Cream",
            "watson_material": "Premium Blackout",  // optional
            "watson_colour": "Ivory"  // optional
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        if 'product_code' not in data:
            return jsonify({'error': "Missing required field 'product_code'"}), 400

        # Get updater info from request (typically set by calling bot)
        updated_by = data.get('updated_by') or request.headers.get('X-Updated-By')

        fabric_id, was_created = db.upsert_fabric(data, updated_by)

        # Get the updated fabric
        fabric = db.get_fabric_by_code(data['product_code'])

        return jsonify({
            'success': True,
            'created': was_created,
            'fabric': format_fabric_response(fabric)
        }), 201 if was_created else 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Error upserting fabric")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics', methods=['DELETE'])
@api_key_required
def delete_fabric():
    """
    Delete a fabric description.

    Query parameters:
        code (required): Product code to delete
    """
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': "Missing required parameter 'code'"}), 400

        deleted = db.delete_fabric(code)

        if deleted:
            return jsonify({
                'success': True,
                'message': f"Fabric description deleted: {code.strip().upper()}"
            })
        else:
            return jsonify({
                'error': f"Fabric not found: {code.strip().upper()}"
            }), 404

    except Exception as e:
        logger.exception(f"Error deleting fabric {request.args.get('code')}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics/bulk', methods=['POST'])
@api_key_required
def bulk_fabrics():
    """
    Bulk operations for fabric descriptions.

    For lookup:
        {
            "operation": "lookup",
            "codes": ["FAB001", "FAB002", ...]
        }

    For upsert:
        {
            "operation": "upsert",
            "fabrics": [
                {"product_code": "FAB001", "supplier_material": "...", ...},
                ...
            ]
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        operation = data.get('operation', 'lookup')

        if operation == 'lookup':
            codes = data.get('codes', [])
            if not isinstance(codes, list):
                return jsonify({'error': "'codes' must be a list"}), 400

            fabrics = db.get_fabrics_by_codes(codes)
            found_codes = {f['product_code'] for f in fabrics}
            normalized = [db.normalize_product_code(c) for c in codes if c]
            not_found = [c for c in normalized if c not in found_codes]

            return jsonify({
                'fabrics': [format_fabric_response(f) for f in fabrics],
                'not_found': not_found
            })

        elif operation == 'upsert':
            fabrics = data.get('fabrics', [])
            if not isinstance(fabrics, list):
                return jsonify({'error': "'fabrics' must be a list"}), 400

            updated_by = data.get('updated_by') or request.headers.get('X-Updated-By')
            result = db.bulk_upsert_fabrics(fabrics, updated_by)

            return jsonify({
                'success': True,
                **result
            })

        else:
            return jsonify({'error': f"Unknown operation: {operation}"}), 400

    except Exception as e:
        logger.exception("Error in bulk fabric operation")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics/search', methods=['GET'])
@api_key_required
def search_fabrics():
    """
    Search fabric descriptions.

    Query parameters:
        q (optional): General search term
        supplier_material (optional): Filter by supplier material
        watson_material (optional): Filter by watson material
        fabric_type (optional): Filter by fabric type (e.g., "Roller", "Awning")
        price_category (optional): Filter by price category (e.g., "A", "B")
        limit (optional): Max results (default 100, max 500)
    """
    try:
        query = request.args.get('q')
        supplier_material = request.args.get('supplier_material')
        watson_material = request.args.get('watson_material')
        fabric_type = request.args.get('fabric_type')
        price_category = request.args.get('price_category')
        limit = min(request.args.get('limit', 100, type=int), 500)

        fabrics = db.search_fabrics(
            query=query,
            supplier_material=supplier_material,
            watson_material=watson_material,
            fabric_type=fabric_type,
            price_category=price_category,
            limit=limit
        )

        return jsonify({
            'fabrics': [format_fabric_response(f) for f in fabrics],
            'count': len(fabrics)
        })

    except Exception as e:
        logger.exception("Error searching fabrics")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics/stats', methods=['GET'])
@api_key_required
def get_fabric_stats():
    """Get fabric description statistics"""
    try:
        return jsonify({
            'total_fabrics': db.get_fabric_count()
        })
    except Exception as e:
        logger.exception("Error getting fabric stats")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics/all', methods=['GET'])
@api_key_required
def get_all_fabrics():
    """
    Get all fabric descriptions with pagination.

    Query parameters:
        limit (optional): Max results per page (default 100, max 1000)
        offset (optional): Offset for pagination (default 0)
    """
    try:
        limit = min(request.args.get('limit', 100, type=int), 1000)
        offset = request.args.get('offset', 0, type=int)

        fabrics = db.get_all_fabrics(limit=limit, offset=offset)
        total = db.get_fabric_count()

        return jsonify({
            'fabrics': [format_fabric_response(f) for f in fabrics],
            'count': len(fabrics),
            'total': total,
            'limit': limit,
            'offset': offset
        })

    except Exception as e:
        logger.exception("Error getting all fabrics")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Mavis Integration Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/mavis/status', methods=['GET'])
@api_key_required
def get_mavis_status():
    """Check Mavis connection status"""
    try:
        status = mavis_service.check_connection()
        return jsonify(status)
    except Exception as e:
        logger.exception("Error checking Mavis status")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/mavis/product', methods=['GET'])
@api_key_required
def get_mavis_product():
    """
    Get a product from Mavis.

    Query parameters:
        code (required): Product code
    """
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': "Missing required parameter 'code'"}), 400

        product = mavis_service.get_product(code)

        if product:
            return jsonify(product)
        else:
            return jsonify({
                'error': f"Product not found in Mavis: {code.strip().upper()}"
            }), 404

    except Exception as e:
        logger.exception(f"Error getting Mavis product {request.args.get('code')}")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Sync Endpoints (for Skye scheduler)
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/sync/auto', methods=['POST'])
@api_key_required
def auto_sync():
    """
    Automated sync endpoint for Skye scheduler.

    This endpoint:
    1. Compares Fiona's fabrics with Mavis's valid fabrics
    2. Adds missing fabrics as placeholders
    3. Reports any fabrics flagged for deletion (requires manual review)

    Returns sync results including:
    - fabrics added
    - fabrics flagged for deletion (not automatically deleted)
    - comparison statistics
    """
    try:
        # Compare with Mavis
        comparison = fabric_sync_service.compare_with_mavis()

        if not comparison.get('success'):
            return jsonify({
                'success': False,
                'error': comparison.get('error', 'Failed to compare with Mavis')
            }), 500

        # Add missing fabrics automatically
        add_result = {'added': 0, 'codes': []}
        if comparison.get('missing_count', 0) > 0:
            add_result = fabric_sync_service.add_missing_fabrics(updated_by='skye-auto-sync')

        return jsonify({
            'success': True,
            'sync_time': request.headers.get('X-Request-Time'),
            'comparison': {
                'fiona_count': comparison.get('fiona_count', 0),
                'mavis_count': comparison.get('mavis_count', 0),
                'missing_count': comparison.get('missing_count', 0),
                'flagged_count': comparison.get('flagged_count', 0)
            },
            'added': {
                'count': add_result.get('added', 0),
                'codes': add_result.get('codes', [])[:20]  # Limit to first 20 for response size
            },
            'flagged_for_deletion': {
                'count': comparison.get('flagged_count', 0),
                'codes': comparison.get('flagged_for_deletion', [])[:20],
                'note': 'These require manual review in Fiona admin UI'
            }
        })

    except Exception as e:
        logger.exception("Error in auto sync")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/sync/status', methods=['GET'])
@api_key_required
def sync_status():
    """
    Get current sync status between Fiona and Mavis.

    Returns comparison without making any changes.
    """
    try:
        comparison = fabric_sync_service.compare_with_mavis()

        if not comparison.get('success'):
            return jsonify({
                'success': False,
                'error': comparison.get('error', 'Failed to compare with Mavis')
            }), 500

        incomplete = fabric_sync_service.get_incomplete_fabrics()
        rebadged = fabric_sync_service.get_rebadged_fabrics()

        return jsonify({
            'success': True,
            'fiona_count': comparison.get('fiona_count', 0),
            'mavis_count': comparison.get('mavis_count', 0),
            'missing_count': comparison.get('missing_count', 0),
            'flagged_count': comparison.get('flagged_count', 0),
            'incomplete_count': len(incomplete),
            'rebadged_count': len(rebadged),
            'in_sync': comparison.get('missing_count', 0) == 0 and comparison.get('flagged_count', 0) == 0
        })

    except Exception as e:
        logger.exception("Error getting sync status")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/sync/fabric-types', methods=['POST'])
@api_key_required
def sync_fabric_types():
    """
    Sync Unleashed-derived fields from Mavis to Fiona.

    This endpoint fetches product data from Mavis and syncs:
    - fabric_type: from product_group (e.g., "Fabric - Roller" -> "Roller")
    - price_category: from product_sub_group (e.g., "A", "B", "Premium")
    - width: fabric width in meters

    Can be called by Skye scheduler or manually triggered.
    """
    try:
        result = fabric_sync_service.sync_unleashed_fields()

        if not result.get('success'):
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to sync Unleashed fields')
            }), 500

        return jsonify({
            'success': True,
            'updated': result.get('updated', 0),
            'not_found': result.get('not_found', 0),
            'fabric_types': result.get('fabric_types', []),
            'price_categories': result.get('price_categories', []),
            'errors': result.get('errors')
        })

    except Exception as e:
        logger.exception("Error syncing Unleashed fields")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route('/fabrics/types', methods=['GET'])
@api_key_required
def get_fabric_types():
    """
    Get all distinct fabric types currently in the database.

    Returns a list of fabric types (e.g., ["Awning", "Panel", "Roller", "Vertical"]).
    """
    try:
        fabric_types = fabric_sync_service.get_fabric_types()
        return jsonify({
            'fabric_types': fabric_types,
            'count': len(fabric_types)
        })

    except Exception as e:
        logger.exception("Error getting fabric types")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/fabrics/price-categories', methods=['GET'])
@api_key_required
def get_price_categories():
    """
    Get all distinct price categories currently in the database.

    Returns a list of price categories (e.g., ["A", "B", "C", "Premium"]).
    """
    try:
        price_categories = fabric_sync_service.get_price_categories()
        return jsonify({
            'price_categories': price_categories,
            'count': len(price_categories)
        })

    except Exception as e:
        logger.exception("Error getting price categories")
        return jsonify({'error': str(e)}), 500
