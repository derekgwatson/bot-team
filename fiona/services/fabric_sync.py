"""
Sync service for Fiona
Compares Fiona's fabric descriptions with valid fabrics from Mavis
"""

import logging
from typing import Dict, List, Set
from database.db import db
from services.mavis_service import mavis_service

logger = logging.getLogger(__name__)


class FabricSyncService:
    """
    Service for syncing fabric descriptions with Mavis.

    Identifies:
    - Fabrics in Fiona that are no longer valid in Mavis (flagged for deletion)
    - Valid fabrics in Mavis that don't have descriptions in Fiona (missing)
    - Fabrics in Fiona that are missing supplier description fields (incomplete)
    """

    def compare_with_mavis(self) -> Dict:
        """
        Compare Fiona's fabrics with Mavis's valid fabric list.

        Returns:
            {
                'success': bool,
                'fiona_codes': set of codes in Fiona,
                'mavis_codes': set of valid fabric codes from Mavis,
                'flagged_for_deletion': codes in Fiona but not in Mavis,
                'missing_from_fiona': codes in Mavis but not in Fiona,
                'error': str (if failed)
            }
        """
        # Get codes from Fiona
        fiona_codes = set(db.get_all_product_codes())

        # Get valid fabric codes from Mavis
        mavis_result = mavis_service.get_valid_fabric_codes()

        if 'error' in mavis_result:
            return {
                'success': False,
                'error': mavis_result['error']
            }

        mavis_codes = set(mavis_result.get('codes', []))

        # Find discrepancies
        flagged_for_deletion = fiona_codes - mavis_codes
        missing_from_fiona = mavis_codes - fiona_codes

        return {
            'success': True,
            'fiona_count': len(fiona_codes),
            'mavis_count': len(mavis_codes),
            'flagged_for_deletion': sorted(list(flagged_for_deletion)),
            'flagged_count': len(flagged_for_deletion),
            'missing_from_fiona': sorted(list(missing_from_fiona)),
            'missing_count': len(missing_from_fiona)
        }

    def get_incomplete_fabrics(self) -> List[Dict]:
        """
        Get fabrics that are missing any of the 3 supplier description fields.

        Returns list of fabric records that are missing:
        - supplier_material
        - supplier_material_type
        - supplier_colour
        """
        all_fabrics = db.get_all_fabrics(limit=10000)

        incomplete = []
        for fabric in all_fabrics:
            missing_fields = []
            if not fabric.get('supplier_material'):
                missing_fields.append('supplier_material')
            if not fabric.get('supplier_material_type'):
                missing_fields.append('supplier_material_type')
            if not fabric.get('supplier_colour'):
                missing_fields.append('supplier_colour')

            if missing_fields:
                fabric['missing_fields'] = missing_fields
                incomplete.append(fabric)

        return incomplete

    def get_rebadged_fabrics(self) -> List[Dict]:
        """
        Get fabrics that have Watson names different from supplier names.

        A fabric is "rebadged" if watson_material or watson_colour is set
        and differs from the corresponding supplier field.

        Returns list of fabric records with rebadged names.
        """
        all_fabrics = db.get_all_fabrics(limit=10000)

        rebadged = []
        for fabric in all_fabrics:
            changes = []

            watson_material = (fabric.get('watson_material') or '').strip()
            supplier_material = (fabric.get('supplier_material') or '').strip()
            if watson_material and watson_material.lower() != supplier_material.lower():
                changes.append({
                    'field': 'material',
                    'supplier': supplier_material,
                    'watson': watson_material
                })

            watson_colour = (fabric.get('watson_colour') or '').strip()
            supplier_colour = (fabric.get('supplier_colour') or '').strip()
            if watson_colour and watson_colour.lower() != supplier_colour.lower():
                changes.append({
                    'field': 'colour',
                    'supplier': supplier_colour,
                    'watson': watson_colour
                })

            if changes:
                fabric['rebadged_changes'] = changes
                rebadged.append(fabric)

        return rebadged

    def add_missing_fabrics(self, updated_by: str = None) -> Dict:
        """
        Add placeholder entries for fabrics that exist in Mavis but not in Fiona.

        Args:
            updated_by: Email of user running the sync

        Returns:
            {'success': bool, 'added': int, 'codes': [...], 'error': str}
        """
        comparison = self.compare_with_mavis()

        if not comparison.get('success'):
            return {
                'success': False,
                'error': comparison.get('error', 'Failed to compare with Mavis')
            }

        missing_codes = comparison.get('missing_from_fiona', [])

        if not missing_codes:
            return {
                'success': True,
                'added': 0,
                'message': 'No missing fabrics to add'
            }

        # Add placeholder entries for each missing code
        added = 0
        errors = []

        for code in missing_codes:
            try:
                db.upsert_fabric({
                    'product_code': code,
                    'supplier_material': None,
                    'supplier_material_type': None,
                    'supplier_colour': None,
                    'watson_material': None,
                    'watson_colour': None
                }, updated_by=updated_by)
                added += 1
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})

        return {
            'success': True,
            'added': added,
            'codes': missing_codes,
            'errors': errors if errors else None
        }

    def delete_flagged_fabrics(self, codes: List[str]) -> Dict:
        """
        Delete specific fabric codes that have been reviewed and confirmed for deletion.

        Args:
            codes: List of product codes to delete

        Returns:
            {'success': bool, 'deleted': int, 'errors': [...]}
        """
        deleted = 0
        errors = []

        for code in codes:
            try:
                if db.delete_fabric(code):
                    deleted += 1
                else:
                    errors.append({'code': code, 'error': 'Not found'})
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})

        return {
            'success': True,
            'deleted': deleted,
            'errors': errors if errors else None
        }

    @staticmethod
    def extract_fabric_type(product_group: str) -> str:
        """
        Extract the fabric type from a product_group value.

        Examples:
            'Fabric - Roller' -> 'Roller'
            'Fabric - Awning' -> 'Awning'
            'Fabric - Vertical' -> 'Vertical'
            'Fabric' -> None (no specific type)

        Returns the extracted type or None if no type can be extracted.
        """
        if not product_group:
            return None

        # Product groups for fabrics typically look like "Fabric - Type"
        if ' - ' in product_group:
            parts = product_group.split(' - ', 1)
            if len(parts) == 2:
                return parts[1].strip()

        # If it's just "Fabric" without a subtype, return None
        return None

    def sync_fabric_types(self) -> Dict:
        """
        Sync fabric types from Mavis (Unleashed product_group) to Fiona.
        Note: For full sync including price_category and width, use sync_unleashed_fields().
        """
        return self.sync_unleashed_fields()

    def sync_unleashed_fields(self) -> Dict:
        """
        Sync all Unleashed-derived fields from Mavis to Fiona.

        Fetches all valid fabric products from Mavis and updates:
        - fabric_type: extracted from product_group (e.g., "Fabric - Roller" -> "Roller")
        - price_category: from product_sub_group (e.g., "A", "B", "Premium")
        - width: fabric width in meters

        Returns:
            {
                'success': bool,
                'updated': int,
                'not_found': int,
                'fabric_types': list of distinct types,
                'price_categories': list of distinct categories,
                'error': str (if failed)
            }
        """
        logger.info("Starting Unleashed fields sync from Mavis")

        # Get all valid fabric products from Mavis
        mavis_result = mavis_service.get_valid_fabric_products()

        if 'error' in mavis_result:
            logger.error(f"Failed to get fabric products from Mavis: {mavis_result['error']}")
            return {
                'success': False,
                'error': mavis_result['error']
            }

        products = mavis_result.get('products', [])
        logger.info(f"Received {len(products)} fabric products from Mavis")

        # Build update list with all fields
        updates = []
        fabric_types = set()
        price_categories = set()

        for product in products:
            code = product.get('product_code')
            if not code:
                continue

            # Extract fabric type from product_group
            product_group = product.get('product_group', '')
            fabric_type = self.extract_fabric_type(product_group)

            # Get price category from product_sub_group
            price_category = product.get('product_sub_group')

            # Get width
            width = product.get('width')

            updates.append({
                'product_code': code,
                'fabric_type': fabric_type,
                'price_category': price_category,
                'width': width
            })

            if fabric_type:
                fabric_types.add(fabric_type)
            if price_category:
                price_categories.add(price_category)

        logger.info(f"Prepared {len(updates)} updates: {len(fabric_types)} types, {len(price_categories)} price categories")

        # Bulk update the database
        result = db.bulk_update_unleashed_fields(updates)

        logger.info(f"Unleashed fields sync complete: {result['updated']} updated, {result['not_found']} not in Fiona")

        return {
            'success': True,
            'updated': result['updated'],
            'not_found': result['not_found'],
            'fabric_types': sorted(list(fabric_types)),
            'price_categories': sorted(list(price_categories)),
            'errors': result.get('errors')
        }

    def get_fabric_types(self) -> List[str]:
        """Get all distinct fabric types currently in the database."""
        return db.get_distinct_fabric_types()

    def get_price_categories(self) -> List[str]:
        """Get all distinct price categories currently in the database."""
        return db.get_distinct_price_categories()

    def get_widths(self) -> List[float]:
        """Get all distinct widths currently in the database."""
        return db.get_distinct_widths()


# Global service instance
fabric_sync_service = FabricSyncService()
