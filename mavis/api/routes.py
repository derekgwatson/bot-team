"""
API Routes for Mavis

REST API for Unleashed data integration:
- Sync management
- Product lookups
"""

from flask import Blueprint, jsonify, request
import logging

from database.db import db
from services.sync_service import sync_service
from shared.auth.bot_api import api_key_required

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Bot Introduction
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/intro', methods=['GET'])
@api_key_required
def intro():
    """Return Mavis's introduction"""
    return jsonify({
        'name': 'Mavis',
        'role': 'Unleashed Data Integration Bot',
        'description': (
            'I sync product data from the Unleashed API and serve it to other bots. '
            'Use me when you need Unleashed product information - I provide a stable, '
            'normalized API so you don\'t have to talk to Unleashed directly.'
        ),
        'capabilities': [
            'Sync products from Unleashed',
            'Lookup products by code',
            'Bulk product lookups',
            'Track sync status',
            'Get changed products since timestamp'
        ],
        'endpoints': {
            'POST /api/sync/run': 'Trigger a full product sync',
            'GET /api/sync/status': 'Get current sync status',
            'GET /api/sync/history': 'Get sync history',
            'GET /api/products': 'Get a product by code (?code=XXX)',
            'POST /api/products/bulk': 'Bulk lookup products by codes',
            'GET /api/products/changed-since': 'Get products changed since timestamp'
        }
    })


# ─────────────────────────────────────────────────────────────────────────────
# Sync Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route('/sync/run', methods=['POST'])
@api_key_required
def run_sync():
    """
    Trigger a full products sync from Unleashed.

    If a sync is already running, returns 409 Conflict.
    """
    try:
        if sync_service.is_running():
            return jsonify({
                'status': 'conflict',
                'message': 'A sync is already in progress',
                'sync_status': sync_service.get_status()
            }), 409

        # Run the sync (synchronously for now)
        result = sync_service.run_product_sync()

        if result['success']:
            return jsonify({
                'status': 'completed',
                'message': 'Product sync completed successfully',
                **result
            })
        else:
            return jsonify({
                'status': 'failed',
                'message': 'Product sync failed',
                **result
            }), 500

    except Exception as e:
        logger.exception("Error running sync")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/status', methods=['GET'])
@api_key_required
def get_sync_status():
    """Get current sync status"""
    try:
        status = sync_service.get_status()
        return jsonify(status)
    except Exception as e:
        logger.exception("Error getting sync status")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/history', methods=['GET'])
@api_key_required
def get_sync_history():
    """Get sync history"""
    try:
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 100)  # Cap at 100

        history = sync_service.get_sync_history(limit)
        return jsonify({
            'history': history,
            'count': len(history)
        })
    except Exception as e:
        logger.exception("Error getting sync history")
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# Product Endpoints
# ─────────────────────────────────────────────────────────────────────────────

def format_product_response(product: dict) -> dict:
    """Format a product record for API response (exclude raw_payload)"""
    return {
        'product_code': product['product_code'],
        'product_description': product['product_description'],
        'product_group': product['product_group'],
        'product_sub_group': product.get('product_sub_group'),
        'default_sell_price': product['default_sell_price'],
        'sell_price_tier_9': product['sell_price_tier_9'],
        'unit_of_measure': product['unit_of_measure'],
        'width': product['width'],
        'updated_at': product['updated_at']
    }


@api_bp.route('/products', methods=['GET'])
@api_key_required
def get_product():
    """
    Get a single product by code.

    Query parameters:
        code (required): Product code (case-insensitive)
    """
    try:
        code = request.args.get('code')
        if not code:
            return jsonify({'error': "Missing required parameter 'code'"}), 400

        product = db.get_product_by_code(code)
        if not product:
            return jsonify({
                'error': f"Product not found: {code.strip().upper()}"
            }), 404

        return jsonify(format_product_response(product))

    except Exception as e:
        logger.exception(f"Error getting product {request.args.get('code')}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/bulk', methods=['POST'])
@api_key_required
def get_products_bulk():
    """
    Bulk lookup products by codes.

    Request body:
        {
            "codes": ["CODE1", "CODE2", ...]
        }

    Response:
        {
            "products": [...],
            "not_found": ["CODE3", ...]
        }
    """
    try:
        data = request.get_json()
        if not data or 'codes' not in data:
            return jsonify({'error': "Missing required field 'codes'"}), 400

        codes = data['codes']
        if not isinstance(codes, list):
            return jsonify({'error': "'codes' must be a list"}), 400

        if not codes:
            return jsonify({'products': [], 'not_found': []})

        # Normalize requested codes for comparison
        normalized_codes = [db.normalize_product_code(c) for c in codes if c]

        # Get products
        products = db.get_products_by_codes(codes)
        found_codes = {p['product_code'] for p in products}

        # Find not found codes
        not_found = [c for c in normalized_codes if c not in found_codes]

        return jsonify({
            'products': [format_product_response(p) for p in products],
            'not_found': not_found
        })

    except Exception as e:
        logger.exception("Error in bulk product lookup")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/changed-since', methods=['GET'])
@api_key_required
def get_products_changed_since():
    """
    Get products changed since a given timestamp.

    Query parameters:
        timestamp (required): ISO8601 UTC timestamp (e.g., 2025-01-15T10:00:00Z)
    """
    try:
        timestamp = request.args.get('timestamp')
        if not timestamp:
            return jsonify({'error': "Missing required parameter 'timestamp'"}), 400

        products = db.get_products_changed_since(timestamp)

        return jsonify({
            'products': [format_product_response(p) for p in products],
            'count': len(products),
            'since': timestamp
        })

    except Exception as e:
        logger.exception("Error getting changed products")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/stats', methods=['GET'])
@api_key_required
def get_product_stats():
    """Get product statistics"""
    try:
        return jsonify({
            'total_products': db.get_product_count()
        })
    except Exception as e:
        logger.exception("Error getting product stats")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/fabrics', methods=['GET'])
@api_key_required
def get_valid_fabrics():
    """
    Get all valid fabric products.

    Valid fabrics are products where:
    - product_group starts with 'Fabric' (case-insensitive)
    - is_obsolete = false
    - is_sellable = true
    - product_sub_group != 'ignore' (case-insensitive)

    Query parameters:
        codes_only (optional): If 'true', return just product codes
    """
    try:
        codes_only = request.args.get('codes_only', '').lower() == 'true'

        if codes_only:
            codes = db.get_valid_fabric_codes()
            return jsonify({
                'codes': codes,
                'count': len(codes)
            })
        else:
            fabrics = db.get_valid_fabric_products()
            return jsonify({
                'products': [format_product_response(f) for f in fabrics],
                'count': len(fabrics)
            })

    except Exception as e:
        logger.exception("Error getting valid fabrics")
        return jsonify({'error': str(e)}), 500
