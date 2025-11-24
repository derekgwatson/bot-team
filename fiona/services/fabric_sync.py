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


# Global service instance
fabric_sync_service = FabricSyncService()
