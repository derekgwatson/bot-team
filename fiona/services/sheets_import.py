"""
Google Sheets import service for Fiona
Imports fabric descriptions from the master spreadsheet
"""

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import config
from database.db import db
import os
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class SheetsImportService:
    """Service for importing fabric descriptions from Google Sheets"""

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

    def __init__(self):
        self.credentials = None
        self.service = None
        self._initialized = False
        self._init_error = None

    def _initialize(self):
        """Initialize Google Sheets API credentials and service"""
        if self._initialized:
            return

        try:
            if not os.path.exists(config.google_credentials_file):
                self._init_error = f"Credentials file not found at {config.google_credentials_file}"
                logger.warning(self._init_error)
                self._initialized = True
                return

            # Create credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                config.google_credentials_file,
                scopes=self.SCOPES
            )

            # Build the Sheets API service
            self.service = build('sheets', 'v4', credentials=self.credentials)
            self._initialized = True

        except Exception as e:
            self._init_error = str(e)
            logger.error(f"Error initializing Google Sheets service: {e}")
            self._initialized = True

    def is_available(self) -> Dict:
        """Check if the import service is available"""
        self._initialize()
        if self.service:
            return {
                'available': True,
                'spreadsheet_id': config.spreadsheet_id,
                'sheet_name': config.sheet_name
            }
        else:
            return {
                'available': False,
                'error': self._init_error or 'Service not initialized'
            }

    def get_sheet_data(self) -> Dict:
        """
        Fetch all data from the Friendly_Descriptions sheet.

        Expected columns:
        A: Product Code (Unleashed code)
        D: FD1 (supplier material)
        E: FD2 (supplier material type)
        F: FD3 (supplier colour)
        G: Watson FD1 (watson material)
        I: Watson FD3 (watson colour)

        Returns dict with 'rows' list or 'error' string
        """
        self._initialize()

        if not self.service:
            return {'error': self._init_error or 'Google Sheets service not available'}

        if not config.spreadsheet_id:
            return {'error': 'Spreadsheet ID not configured'}

        try:
            # Fetch columns A, D, E, F, G, I (we need to fetch A:I and pick the ones we want)
            range_name = f"{config.sheet_name}!A:I"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=config.spreadsheet_id,
                range=range_name
            ).execute()

            rows = result.get('values', [])

            if not rows:
                return {'rows': [], 'message': 'Sheet is empty'}

            return {'rows': rows, 'count': len(rows)}

        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            return {'error': f'API error: {e}'}
        except Exception as e:
            logger.exception("Error fetching sheet data")
            return {'error': f'Unexpected error: {e}'}

    def parse_sheet_data(self, rows: List) -> List[Dict]:
        """
        Parse raw sheet rows into fabric description records.

        Column mapping:
        A (0): Product Code
        D (3): FD1 - supplier material
        E (4): FD2 - supplier material type
        F (5): FD3 - supplier colour
        G (6): Watson FD1 - watson material
        I (8): Watson FD3 - watson colour
        """
        fabrics = []
        skipped = 0

        for i, row in enumerate(rows):
            # Skip header row (row 0)
            if i == 0:
                continue

            # Pad row to 9 columns if needed
            while len(row) < 9:
                row.append('')

            product_code = row[0].strip() if row[0] else ''

            # Skip rows without product code
            if not product_code:
                skipped += 1
                continue

            fabric = {
                'product_code': product_code.upper(),
                'supplier_material': row[3].strip() if len(row) > 3 and row[3] else None,
                'supplier_material_type': row[4].strip() if len(row) > 4 and row[4] else None,
                'supplier_colour': row[5].strip() if len(row) > 5 and row[5] else None,
                'watson_material': row[6].strip() if len(row) > 6 and row[6] else None,
                'watson_colour': row[8].strip() if len(row) > 8 and row[8] else None,
            }

            # Only include if at least one description field is set
            has_data = any([
                fabric['supplier_material'],
                fabric['supplier_material_type'],
                fabric['supplier_colour'],
                fabric['watson_material'],
                fabric['watson_colour']
            ])

            if has_data:
                fabrics.append(fabric)
            else:
                skipped += 1

        return fabrics

    def run_import(self, updated_by: str = None, dry_run: bool = False) -> Dict:
        """
        Import fabric descriptions from the Google Sheet.

        Args:
            updated_by: Email of user running the import
            dry_run: If True, don't actually save to database

        Returns:
            Import result with stats
        """
        # Fetch data from sheet
        sheet_result = self.get_sheet_data()

        if 'error' in sheet_result:
            return {
                'success': False,
                'error': sheet_result['error']
            }

        rows = sheet_result.get('rows', [])
        if not rows:
            return {
                'success': True,
                'message': 'No data in sheet',
                'stats': {'total': 0, 'imported': 0, 'skipped': 0}
            }

        # Parse rows into fabric records
        fabrics = self.parse_sheet_data(rows)

        if dry_run:
            return {
                'success': True,
                'dry_run': True,
                'message': f'Would import {len(fabrics)} fabric descriptions',
                'stats': {
                    'total_rows': len(rows),
                    'fabrics_found': len(fabrics)
                },
                'preview': fabrics[:10]  # First 10 for preview
            }

        # Perform the import
        result = db.bulk_upsert_fabrics(fabrics, updated_by=updated_by)

        return {
            'success': True,
            'message': f"Imported {result['created']} new, updated {result['updated']} existing fabric descriptions",
            'stats': {
                'total_rows': len(rows),
                'fabrics_found': len(fabrics),
                'created': result['created'],
                'updated': result['updated'],
                'errors': len(result['errors'])
            },
            'errors': result['errors'][:10] if result['errors'] else []  # First 10 errors
        }


# Singleton instance
sheets_import_service = SheetsImportService()
