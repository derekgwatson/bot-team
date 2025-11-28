"""
Parser service for processing Buz inventory and pricing Excel exports.

Parses Excel files exported from Buz and extracts inventory items and
pricing coefficients into structured data.
"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


class BuzExcelParser:
    """
    Parser for Buz Excel exports.

    Handles both inventory items and pricing coefficients exports.
    The parser is flexible to handle varying column structures.
    """

    # Common column name mappings for inventory items
    INVENTORY_COLUMN_MAP = {
        # Code columns
        'inventory group code': 'group_code',
        'inventorygroupcode': 'group_code',
        'group code': 'group_code',
        'group': 'group_code',
        'item code': 'item_code',
        'itemcode': 'item_code',
        'code': 'item_code',
        'product code': 'item_code',

        # Name columns
        'item name': 'item_name',
        'itemname': 'item_name',
        'name': 'item_name',
        'product name': 'item_name',
        'description': 'description',
        'item description': 'description',

        # Status columns
        'is current': 'is_active',
        'iscurrent': 'is_active',
        'current': 'is_active',
        'active': 'is_active',
        'status': 'is_active',

        # Pricing columns
        'cost price': 'cost_price',
        'costprice': 'cost_price',
        'cost': 'cost_price',
        'sell price': 'sell_price',
        'sellprice': 'sell_price',
        'price': 'sell_price',

        # Quantity columns
        'min qty': 'min_qty',
        'minqty': 'min_qty',
        'minimum': 'min_qty',
        'min': 'min_qty',
        'max qty': 'max_qty',
        'maxqty': 'max_qty',
        'maximum': 'max_qty',
        'max': 'max_qty',

        # Supplier columns
        'supplier code': 'supplier_code',
        'suppliercode': 'supplier_code',
        'supplier name': 'supplier_name',
        'suppliername': 'supplier_name',
        'supplier': 'supplier_name',

        # Other columns
        'unit of measure': 'unit_of_measure',
        'uom': 'unit_of_measure',
        'unit': 'unit_of_measure',
        'sort order': 'sort_order',
        'sortorder': 'sort_order',
        'order': 'sort_order',
    }

    # Common column name mappings for pricing coefficients
    PRICING_COLUMN_MAP = {
        # Group columns
        'inventory group code': 'group_code',
        'inventorygroupcode': 'group_code',
        'group code': 'group_code',
        'group': 'group_code',
        'layout': 'group_code',

        # Coefficient columns
        'coefficient code': 'coefficient_code',
        'coefficientcode': 'coefficient_code',
        'code': 'coefficient_code',
        'pricing code': 'coefficient_code',
        'coefficient name': 'coefficient_name',
        'coefficientname': 'coefficient_name',
        'name': 'coefficient_name',
        'pricing name': 'coefficient_name',

        # Description columns
        'description': 'description',
        'coefficient description': 'description',

        # Type columns
        'type': 'coefficient_type',
        'coefficient type': 'coefficient_type',

        # Status columns
        'is current': 'is_active',
        'iscurrent': 'is_active',
        'current': 'is_active',
        'active': 'is_active',
        'status': 'is_active',

        # Value columns
        'value': 'base_value',
        'base value': 'base_value',
        'basevalue': 'base_value',
        'coefficient': 'base_value',
        'min value': 'min_value',
        'minvalue': 'min_value',
        'minimum': 'min_value',
        'max value': 'max_value',
        'maxvalue': 'max_value',
        'maximum': 'max_value',

        # Other columns
        'unit': 'unit',
        'uom': 'unit',
        'sort order': 'sort_order',
        'sortorder': 'sort_order',
        'order': 'sort_order',
    }

    def parse_inventory_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an inventory items Excel file.

        Args:
            file_path: Path to the Excel file

        Returns:
            Dict with items list and metadata
        """
        logger.info(f"Parsing inventory file: {file_path}")

        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            items = []
            groups = {}

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_items = self._parse_inventory_sheet(sheet, sheet_name)
                items.extend(sheet_items)

                # Track groups
                for item in sheet_items:
                    group_code = item.get('group_code', sheet_name)
                    if group_code not in groups:
                        groups[group_code] = {
                            'group_code': group_code,
                            'group_name': group_code,
                            'item_count': 0
                        }
                    groups[group_code]['item_count'] += 1

            workbook.close()

            logger.info(f"Parsed {len(items)} inventory items from {len(groups)} groups")

            return {
                'success': True,
                'items': items,
                'groups': list(groups.values()),
                'total_items': len(items),
                'total_groups': len(groups)
            }

        except Exception as e:
            logger.exception(f"Error parsing inventory file: {e}")
            return {
                'success': False,
                'error': str(e),
                'items': [],
                'groups': []
            }

    def parse_pricing_file(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a pricing coefficients Excel file.

        Args:
            file_path: Path to the Excel file

        Returns:
            Dict with coefficients list and metadata
        """
        logger.info(f"Parsing pricing file: {file_path}")

        try:
            workbook = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            coefficients = []
            groups = {}

            for sheet_name in workbook.sheetnames:
                sheet = workbook[sheet_name]
                sheet_coefficients = self._parse_pricing_sheet(sheet, sheet_name)
                coefficients.extend(sheet_coefficients)

                # Track groups
                for coeff in sheet_coefficients:
                    group_code = coeff.get('group_code', sheet_name)
                    if group_code not in groups:
                        groups[group_code] = {
                            'group_code': group_code,
                            'group_name': group_code,
                            'coefficient_count': 0
                        }
                    groups[group_code]['coefficient_count'] += 1

            workbook.close()

            logger.info(f"Parsed {len(coefficients)} pricing coefficients from {len(groups)} groups")

            return {
                'success': True,
                'coefficients': coefficients,
                'groups': list(groups.values()),
                'total_coefficients': len(coefficients),
                'total_groups': len(groups)
            }

        except Exception as e:
            logger.exception(f"Error parsing pricing file: {e}")
            return {
                'success': False,
                'error': str(e),
                'coefficients': [],
                'groups': []
            }

    def _parse_inventory_sheet(
        self,
        sheet: Worksheet,
        default_group: str
    ) -> List[Dict[str, Any]]:
        """
        Parse a single sheet of inventory items.

        Args:
            sheet: openpyxl worksheet
            default_group: Default group code if not in data

        Returns:
            List of inventory item dicts
        """
        items = []
        header_row = None
        column_map = {}

        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if not any(row):
                continue

            # Find header row
            if header_row is None:
                if self._looks_like_header(row, self.INVENTORY_COLUMN_MAP):
                    header_row = row_idx
                    column_map = self._build_column_map(row, self.INVENTORY_COLUMN_MAP)
                    logger.debug(f"Found inventory header at row {row_idx}: {column_map}")
                continue

            # Parse data row
            item = self._parse_inventory_row(row, column_map, default_group)
            if item:
                items.append(item)

        return items

    def _parse_pricing_sheet(
        self,
        sheet: Worksheet,
        default_group: str
    ) -> List[Dict[str, Any]]:
        """
        Parse a single sheet of pricing coefficients.

        Args:
            sheet: openpyxl worksheet
            default_group: Default group code if not in data

        Returns:
            List of pricing coefficient dicts
        """
        coefficients = []
        header_row = None
        column_map = {}

        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if not any(row):
                continue

            # Find header row
            if header_row is None:
                if self._looks_like_header(row, self.PRICING_COLUMN_MAP):
                    header_row = row_idx
                    column_map = self._build_column_map(row, self.PRICING_COLUMN_MAP)
                    logger.debug(f"Found pricing header at row {row_idx}: {column_map}")
                continue

            # Parse data row
            coeff = self._parse_pricing_row(row, column_map, default_group)
            if coeff:
                coefficients.append(coeff)

        return coefficients

    def _looks_like_header(self, row: tuple, mapping: Dict[str, str]) -> bool:
        """Check if a row looks like a header based on known column names."""
        if not row:
            return False

        matches = 0
        for cell in row:
            if cell and isinstance(cell, str):
                normalized = cell.lower().strip()
                if normalized in mapping:
                    matches += 1

        # Consider it a header if we match at least 2 columns
        return matches >= 2

    def _build_column_map(
        self,
        header_row: tuple,
        mapping: Dict[str, str]
    ) -> Dict[int, str]:
        """
        Build a mapping of column index to field name.

        Args:
            header_row: Tuple of header values
            mapping: Dict of header name -> field name

        Returns:
            Dict of column_index -> field_name
        """
        column_map = {}
        for idx, cell in enumerate(header_row):
            if cell and isinstance(cell, str):
                normalized = cell.lower().strip()
                if normalized in mapping:
                    column_map[idx] = mapping[normalized]
        return column_map

    def _parse_inventory_row(
        self,
        row: tuple,
        column_map: Dict[int, str],
        default_group: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single inventory item row."""
        item = {
            'group_code': default_group,
            'item_code': '',
            'item_name': '',
            'description': '',
            'unit_of_measure': '',
            'is_active': True,
            'supplier_code': '',
            'supplier_name': '',
            'cost_price': 0.0,
            'sell_price': 0.0,
            'min_qty': 0.0,
            'max_qty': 0.0,
            'sort_order': 0,
            'extra_data': {}
        }

        unmapped = {}

        for idx, value in enumerate(row):
            if idx in column_map:
                field = column_map[idx]
                item[field] = self._convert_value(value, field)
            elif value is not None:
                # Store unmapped columns in extra_data
                unmapped[f'col_{idx}'] = value

        if unmapped:
            item['extra_data'] = unmapped

        # Item must have at least a code or name
        if not item['item_code'] and not item['item_name']:
            return None

        # If no item_code, derive from name
        if not item['item_code'] and item['item_name']:
            item['item_code'] = item['item_name'][:50]

        return item

    def _parse_pricing_row(
        self,
        row: tuple,
        column_map: Dict[int, str],
        default_group: str
    ) -> Optional[Dict[str, Any]]:
        """Parse a single pricing coefficient row."""
        coeff = {
            'group_code': default_group,
            'coefficient_code': '',
            'coefficient_name': '',
            'description': '',
            'coefficient_type': '',
            'is_active': True,
            'base_value': 0.0,
            'min_value': 0.0,
            'max_value': 0.0,
            'unit': '',
            'sort_order': 0,
            'extra_data': {}
        }

        unmapped = {}

        for idx, value in enumerate(row):
            if idx in column_map:
                field = column_map[idx]
                coeff[field] = self._convert_value(value, field)
            elif value is not None:
                # Store unmapped columns in extra_data
                unmapped[f'col_{idx}'] = value

        if unmapped:
            coeff['extra_data'] = unmapped

        # Coefficient must have at least a code or name
        if not coeff['coefficient_code'] and not coeff['coefficient_name']:
            return None

        # If no code, derive from name
        if not coeff['coefficient_code'] and coeff['coefficient_name']:
            coeff['coefficient_code'] = coeff['coefficient_name'][:50]

        return coeff

    def _convert_value(self, value: Any, field: str) -> Any:
        """Convert a cell value to the appropriate type for a field."""
        if value is None:
            # Return appropriate default based on field type
            if field in ('is_active',):
                return True
            elif field in ('cost_price', 'sell_price', 'min_qty', 'max_qty',
                          'base_value', 'min_value', 'max_value'):
                return 0.0
            elif field in ('sort_order',):
                return 0
            return ''

        # Boolean fields
        if field == 'is_active':
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                return value.lower() in ('yes', 'true', '1', 'y', 'active', 'current')
            return True

        # Numeric fields
        if field in ('cost_price', 'sell_price', 'min_qty', 'max_qty',
                    'base_value', 'min_value', 'max_value'):
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0.0

        if field == 'sort_order':
            try:
                return int(value)
            except (ValueError, TypeError):
                return 0

        # String fields
        return str(value).strip() if value else ''


# Singleton instance
parser = BuzExcelParser()
