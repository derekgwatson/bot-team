"""
Database service for Ivy's Buz inventory and pricing cache.
"""
import sqlite3
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from shared.migrations import MigrationRunner


class InventoryDatabase:
    """SQLite database for caching Buz inventory and pricing data."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), 'ivy.db')
        self.db_path = db_path
        self._ensure_database()

    def _ensure_database(self):
        """Ensure database and tables exist using migrations."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        migrations_dir = os.path.join(os.path.dirname(__file__), '..', 'migrations')
        runner = MigrationRunner(db_path=self.db_path, migrations_dir=migrations_dir)
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # =====================
    # Inventory Group Operations
    # =====================

    def upsert_inventory_group(
        self,
        org_key: str,
        group_code: str,
        group_name: str,
        is_active: bool = True,
        item_count: int = 0
    ) -> Dict[str, Any]:
        """Insert or update an inventory group."""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT id FROM inventory_groups WHERE org_key = ? AND group_code = ?',
            (org_key, group_code)
        )
        existing = cursor.fetchone()

        if existing:
            conn.execute('''
                UPDATE inventory_groups SET
                    group_name = ?,
                    is_active = ?,
                    item_count = ?,
                    last_synced = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE org_key = ? AND group_code = ?
            ''', (group_name, 1 if is_active else 0, item_count, org_key, group_code))
            action = 'updated'
        else:
            conn.execute('''
                INSERT INTO inventory_groups (org_key, group_code, group_name, is_active, item_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (org_key, group_code, group_name, 1 if is_active else 0, item_count))
            action = 'created'

        conn.commit()
        conn.close()
        return {'success': True, 'action': action}

    def get_inventory_groups(self, org_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get inventory groups with optional org filter."""
        conn = self.get_connection()
        if org_key:
            cursor = conn.execute(
                'SELECT * FROM inventory_groups WHERE org_key = ? ORDER BY group_name',
                (org_key,)
            )
        else:
            cursor = conn.execute('SELECT * FROM inventory_groups ORDER BY org_key, group_name')
        groups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return groups

    # =====================
    # Inventory Item Operations
    # =====================

    def upsert_inventory_item(
        self,
        org_key: str,
        group_code: str,
        item_code: str,
        item_name: str,
        description: str = '',
        unit_of_measure: str = '',
        is_active: bool = True,
        supplier_code: str = '',
        supplier_name: str = '',
        cost_price: float = 0,
        sell_price: float = 0,
        min_qty: float = 0,
        max_qty: float = 0,
        sort_order: int = 0,
        extra_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Insert or update an inventory item."""
        conn = self.get_connection()
        extra_json = json.dumps(extra_data or {})

        cursor = conn.execute(
            'SELECT id FROM inventory_items WHERE org_key = ? AND group_code = ? AND item_code = ?',
            (org_key, group_code, item_code)
        )
        existing = cursor.fetchone()

        if existing:
            conn.execute('''
                UPDATE inventory_items SET
                    item_name = ?,
                    description = ?,
                    unit_of_measure = ?,
                    is_active = ?,
                    supplier_code = ?,
                    supplier_name = ?,
                    cost_price = ?,
                    sell_price = ?,
                    min_qty = ?,
                    max_qty = ?,
                    sort_order = ?,
                    extra_data = ?,
                    last_synced = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE org_key = ? AND group_code = ? AND item_code = ?
            ''', (
                item_name, description, unit_of_measure, 1 if is_active else 0,
                supplier_code, supplier_name, cost_price, sell_price,
                min_qty, max_qty, sort_order, extra_json,
                org_key, group_code, item_code
            ))
            action = 'updated'
        else:
            conn.execute('''
                INSERT INTO inventory_items (
                    org_key, group_code, item_code, item_name, description,
                    unit_of_measure, is_active, supplier_code, supplier_name,
                    cost_price, sell_price, min_qty, max_qty, sort_order, extra_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                org_key, group_code, item_code, item_name, description,
                unit_of_measure, 1 if is_active else 0, supplier_code, supplier_name,
                cost_price, sell_price, min_qty, max_qty, sort_order, extra_json
            ))
            action = 'created'

        conn.commit()
        conn.close()
        return {'success': True, 'action': action}

    def bulk_upsert_inventory_items(
        self,
        org_key: str,
        items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Bulk upsert inventory items from a sync operation."""
        conn = self.get_connection()
        created = 0
        updated = 0

        for item in items:
            extra_json = json.dumps(item.get('extra_data', {}))

            cursor = conn.execute(
                'SELECT id FROM inventory_items WHERE org_key = ? AND group_code = ? AND item_code = ?',
                (org_key, item['group_code'], item['item_code'])
            )
            existing = cursor.fetchone()

            if existing:
                conn.execute('''
                    UPDATE inventory_items SET
                        item_name = ?,
                        description = ?,
                        unit_of_measure = ?,
                        is_active = ?,
                        supplier_code = ?,
                        supplier_name = ?,
                        cost_price = ?,
                        sell_price = ?,
                        min_qty = ?,
                        max_qty = ?,
                        sort_order = ?,
                        extra_data = ?,
                        last_synced = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE org_key = ? AND group_code = ? AND item_code = ?
                ''', (
                    item.get('item_name', ''),
                    item.get('description', ''),
                    item.get('unit_of_measure', ''),
                    1 if item.get('is_active', True) else 0,
                    item.get('supplier_code', ''),
                    item.get('supplier_name', ''),
                    item.get('cost_price', 0),
                    item.get('sell_price', 0),
                    item.get('min_qty', 0),
                    item.get('max_qty', 0),
                    item.get('sort_order', 0),
                    extra_json,
                    org_key, item['group_code'], item['item_code']
                ))
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO inventory_items (
                        org_key, group_code, item_code, item_name, description,
                        unit_of_measure, is_active, supplier_code, supplier_name,
                        cost_price, sell_price, min_qty, max_qty, sort_order, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    org_key, item['group_code'], item['item_code'],
                    item.get('item_name', ''), item.get('description', ''),
                    item.get('unit_of_measure', ''),
                    1 if item.get('is_active', True) else 0,
                    item.get('supplier_code', ''), item.get('supplier_name', ''),
                    item.get('cost_price', 0), item.get('sell_price', 0),
                    item.get('min_qty', 0), item.get('max_qty', 0),
                    item.get('sort_order', 0), extra_json
                ))
                created += 1

        conn.commit()
        conn.close()

        return {
            'success': True,
            'org_key': org_key,
            'created': created,
            'updated': updated,
            'total': created + updated
        }

    def get_inventory_items(
        self,
        org_key: Optional[str] = None,
        group_code: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get inventory items with optional filters."""
        conn = self.get_connection()

        query = 'SELECT * FROM inventory_items WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if group_code:
            query += ' AND group_code = ?'
            params.append(group_code)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        if search:
            query += ' AND (item_code LIKE ? OR item_name LIKE ? OR description LIKE ?)'
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])

        query += ' ORDER BY org_key, group_code, sort_order, item_name'
        query += f' LIMIT {limit} OFFSET {offset}'

        cursor = conn.execute(query, params)
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parse extra_data JSON
        for item in items:
            if item.get('extra_data'):
                try:
                    item['extra_data'] = json.loads(item['extra_data'])
                except json.JSONDecodeError:
                    item['extra_data'] = {}

        return items

    def get_inventory_item(
        self,
        org_key: str,
        group_code: str,
        item_code: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single inventory item."""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT * FROM inventory_items WHERE org_key = ? AND group_code = ? AND item_code = ?',
            (org_key, group_code, item_code)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            item = dict(row)
            if item.get('extra_data'):
                try:
                    item['extra_data'] = json.loads(item['extra_data'])
                except json.JSONDecodeError:
                    item['extra_data'] = {}
            return item
        return None

    def get_inventory_item_count(
        self,
        org_key: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """Get count of inventory items."""
        conn = self.get_connection()

        query = 'SELECT COUNT(*) as count FROM inventory_items WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        cursor = conn.execute(query, params)
        count = cursor.fetchone()['count']
        conn.close()
        return count

    # =====================
    # Pricing Group Operations
    # =====================

    def upsert_pricing_group(
        self,
        org_key: str,
        group_code: str,
        group_name: str,
        is_active: bool = True,
        coefficient_count: int = 0
    ) -> Dict[str, Any]:
        """Insert or update a pricing group."""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT id FROM pricing_groups WHERE org_key = ? AND group_code = ?',
            (org_key, group_code)
        )
        existing = cursor.fetchone()

        if existing:
            conn.execute('''
                UPDATE pricing_groups SET
                    group_name = ?,
                    is_active = ?,
                    coefficient_count = ?,
                    last_synced = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE org_key = ? AND group_code = ?
            ''', (group_name, 1 if is_active else 0, coefficient_count, org_key, group_code))
            action = 'updated'
        else:
            conn.execute('''
                INSERT INTO pricing_groups (org_key, group_code, group_name, is_active, coefficient_count)
                VALUES (?, ?, ?, ?, ?)
            ''', (org_key, group_code, group_name, 1 if is_active else 0, coefficient_count))
            action = 'created'

        conn.commit()
        conn.close()
        return {'success': True, 'action': action}

    def get_pricing_groups(self, org_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get pricing groups with optional org filter."""
        conn = self.get_connection()
        if org_key:
            cursor = conn.execute(
                'SELECT * FROM pricing_groups WHERE org_key = ? ORDER BY group_name',
                (org_key,)
            )
        else:
            cursor = conn.execute('SELECT * FROM pricing_groups ORDER BY org_key, group_name')
        groups = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return groups

    # =====================
    # Pricing Coefficient Operations
    # =====================

    def upsert_pricing_coefficient(
        self,
        org_key: str,
        group_code: str,
        coefficient_code: str,
        coefficient_name: str,
        description: str = '',
        coefficient_type: str = '',
        is_active: bool = True,
        base_value: float = 0,
        min_value: float = 0,
        max_value: float = 0,
        unit: str = '',
        sort_order: int = 0,
        extra_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Insert or update a pricing coefficient."""
        conn = self.get_connection()
        extra_json = json.dumps(extra_data or {})

        cursor = conn.execute(
            'SELECT id FROM pricing_coefficients WHERE org_key = ? AND group_code = ? AND coefficient_code = ?',
            (org_key, group_code, coefficient_code)
        )
        existing = cursor.fetchone()

        if existing:
            conn.execute('''
                UPDATE pricing_coefficients SET
                    coefficient_name = ?,
                    description = ?,
                    coefficient_type = ?,
                    is_active = ?,
                    base_value = ?,
                    min_value = ?,
                    max_value = ?,
                    unit = ?,
                    sort_order = ?,
                    extra_data = ?,
                    last_synced = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE org_key = ? AND group_code = ? AND coefficient_code = ?
            ''', (
                coefficient_name, description, coefficient_type, 1 if is_active else 0,
                base_value, min_value, max_value, unit, sort_order, extra_json,
                org_key, group_code, coefficient_code
            ))
            action = 'updated'
        else:
            conn.execute('''
                INSERT INTO pricing_coefficients (
                    org_key, group_code, coefficient_code, coefficient_name, description,
                    coefficient_type, is_active, base_value, min_value, max_value,
                    unit, sort_order, extra_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                org_key, group_code, coefficient_code, coefficient_name, description,
                coefficient_type, 1 if is_active else 0, base_value, min_value, max_value,
                unit, sort_order, extra_json
            ))
            action = 'created'

        conn.commit()
        conn.close()
        return {'success': True, 'action': action}

    def bulk_upsert_pricing_coefficients(
        self,
        org_key: str,
        coefficients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Bulk upsert pricing coefficients from a sync operation."""
        conn = self.get_connection()
        created = 0
        updated = 0

        for coeff in coefficients:
            extra_json = json.dumps(coeff.get('extra_data', {}))

            cursor = conn.execute(
                'SELECT id FROM pricing_coefficients WHERE org_key = ? AND group_code = ? AND coefficient_code = ?',
                (org_key, coeff['group_code'], coeff['coefficient_code'])
            )
            existing = cursor.fetchone()

            if existing:
                conn.execute('''
                    UPDATE pricing_coefficients SET
                        coefficient_name = ?,
                        description = ?,
                        coefficient_type = ?,
                        is_active = ?,
                        base_value = ?,
                        min_value = ?,
                        max_value = ?,
                        unit = ?,
                        sort_order = ?,
                        extra_data = ?,
                        last_synced = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE org_key = ? AND group_code = ? AND coefficient_code = ?
                ''', (
                    coeff.get('coefficient_name', ''),
                    coeff.get('description', ''),
                    coeff.get('coefficient_type', ''),
                    1 if coeff.get('is_active', True) else 0,
                    coeff.get('base_value', 0),
                    coeff.get('min_value', 0),
                    coeff.get('max_value', 0),
                    coeff.get('unit', ''),
                    coeff.get('sort_order', 0),
                    extra_json,
                    org_key, coeff['group_code'], coeff['coefficient_code']
                ))
                updated += 1
            else:
                conn.execute('''
                    INSERT INTO pricing_coefficients (
                        org_key, group_code, coefficient_code, coefficient_name, description,
                        coefficient_type, is_active, base_value, min_value, max_value,
                        unit, sort_order, extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    org_key, coeff['group_code'], coeff['coefficient_code'],
                    coeff.get('coefficient_name', ''), coeff.get('description', ''),
                    coeff.get('coefficient_type', ''),
                    1 if coeff.get('is_active', True) else 0,
                    coeff.get('base_value', 0), coeff.get('min_value', 0),
                    coeff.get('max_value', 0), coeff.get('unit', ''),
                    coeff.get('sort_order', 0), extra_json
                ))
                created += 1

        conn.commit()
        conn.close()

        return {
            'success': True,
            'org_key': org_key,
            'created': created,
            'updated': updated,
            'total': created + updated
        }

    def get_pricing_coefficients(
        self,
        org_key: Optional[str] = None,
        group_code: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get pricing coefficients with optional filters."""
        conn = self.get_connection()

        query = 'SELECT * FROM pricing_coefficients WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if group_code:
            query += ' AND group_code = ?'
            params.append(group_code)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        if search:
            query += ' AND (coefficient_code LIKE ? OR coefficient_name LIKE ? OR description LIKE ?)'
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])

        query += ' ORDER BY org_key, group_code, sort_order, coefficient_name'
        query += f' LIMIT {limit} OFFSET {offset}'

        cursor = conn.execute(query, params)
        coefficients = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Parse extra_data JSON
        for coeff in coefficients:
            if coeff.get('extra_data'):
                try:
                    coeff['extra_data'] = json.loads(coeff['extra_data'])
                except json.JSONDecodeError:
                    coeff['extra_data'] = {}

        return coefficients

    def get_pricing_coefficient(
        self,
        org_key: str,
        group_code: str,
        coefficient_code: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single pricing coefficient."""
        conn = self.get_connection()
        cursor = conn.execute(
            'SELECT * FROM pricing_coefficients WHERE org_key = ? AND group_code = ? AND coefficient_code = ?',
            (org_key, group_code, coefficient_code)
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            coeff = dict(row)
            if coeff.get('extra_data'):
                try:
                    coeff['extra_data'] = json.loads(coeff['extra_data'])
                except json.JSONDecodeError:
                    coeff['extra_data'] = {}
            return coeff
        return None

    def get_pricing_coefficient_count(
        self,
        org_key: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """Get count of pricing coefficients."""
        conn = self.get_connection()

        query = 'SELECT COUNT(*) as count FROM pricing_coefficients WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if is_active is not None:
            query += ' AND is_active = ?'
            params.append(1 if is_active else 0)

        cursor = conn.execute(query, params)
        count = cursor.fetchone()['count']
        conn.close()
        return count

    # =====================
    # Sync Log Operations
    # =====================

    def start_sync(self, org_key: str, sync_type: str, status: str = 'running') -> int:
        """
        Record that a sync has started.

        Args:
            org_key: Organization key
            sync_type: 'inventory' or 'pricing'
            status: Initial status ('running' or 'waiting_for_lock')

        Returns:
            ID of the sync log entry
        """
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO sync_log (org_key, sync_type, status, started_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (org_key, sync_type, status))
        sync_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return sync_id

    def update_sync_status(self, sync_id: int, status: str) -> bool:
        """
        Update the status of a sync log entry.

        Used to transition from 'waiting_for_lock' to 'running'.

        Args:
            sync_id: Sync log ID
            status: New status

        Returns:
            True if updated successfully
        """
        conn = self.get_connection()
        cursor = conn.execute('''
            UPDATE sync_log SET status = ? WHERE id = ?
        ''', (status, sync_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def update_sync_progress(
        self,
        sync_id: int,
        progress: int,
        message: str = ''
    ) -> bool:
        """
        Update sync progress percentage and message.

        Args:
            sync_id: Sync log ID
            progress: Progress percentage (0-100)
            message: Current stage message (e.g., "Parsing row 50 of 100")

        Returns:
            True if updated successfully
        """
        conn = self.get_connection()
        cursor = conn.execute('''
            UPDATE sync_log SET progress = ?, progress_message = ? WHERE id = ?
        ''', (progress, message, sync_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def complete_sync(
        self,
        sync_id: int,
        item_count: int,
        status: str = 'success',
        error_message: str = '',
        duration_seconds: float = 0
    ) -> bool:
        """Complete a running sync with final status."""
        conn = self.get_connection()
        cursor = conn.execute('''
            UPDATE sync_log
            SET item_count = ?, status = ?, error_message = ?,
                duration_seconds = ?, completed_at = CURRENT_TIMESTAMP,
                progress = 100, progress_message = ''
            WHERE id = ?
        ''', (item_count, status, error_message, duration_seconds, sync_id))
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def get_running_syncs(self, org_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get currently running or waiting syncs."""
        conn = self.get_connection()
        if org_key:
            cursor = conn.execute(
                "SELECT * FROM sync_log WHERE status IN ('running', 'waiting_for_lock') AND org_key = ? ORDER BY started_at DESC",
                (org_key,)
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM sync_log WHERE status IN ('running', 'waiting_for_lock') ORDER BY started_at DESC"
            )
        syncs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return syncs

    def get_last_sync(self, org_key: str, sync_type: str) -> Optional[Dict[str, Any]]:
        """Get the last completed sync record for an org and type."""
        conn = self.get_connection()
        cursor = conn.execute(
            '''SELECT * FROM sync_log
               WHERE org_key = ? AND sync_type = ? AND status != 'running'
               ORDER BY completed_at DESC LIMIT 1''',
            (org_key, sync_type)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_sync_history(
        self,
        org_key: Optional[str] = None,
        sync_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get sync history with optional filters."""
        conn = self.get_connection()

        query = 'SELECT * FROM sync_log WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if sync_type:
            query += ' AND sync_type = ?'
            params.append(sync_type)

        query += ' ORDER BY COALESCE(completed_at, started_at) DESC LIMIT ?'
        params.append(limit)

        cursor = conn.execute(query, params)
        history = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return history

    # =====================
    # Activity Log Operations
    # =====================

    def log_activity(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        org_key: str,
        old_value: str = '',
        new_value: str = '',
        performed_by: str = 'system',
        success: bool = True,
        error_message: str = ''
    ) -> int:
        """Log an activity/change."""
        conn = self.get_connection()
        cursor = conn.execute('''
            INSERT INTO activity_log (
                action, entity_type, entity_id, org_key, old_value, new_value,
                performed_by, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            action, entity_type, entity_id, org_key, old_value, new_value,
            performed_by, 1 if success else 0, error_message
        ))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return log_id

    def get_activity_log(
        self,
        org_key: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get activity log with optional filters."""
        conn = self.get_connection()

        query = 'SELECT * FROM activity_log WHERE 1=1'
        params = []

        if org_key:
            query += ' AND org_key = ?'
            params.append(org_key)

        if entity_type:
            query += ' AND entity_type = ?'
            params.append(entity_type)

        query += ' ORDER BY performed_at DESC LIMIT ?'
        params.append(limit)

        cursor = conn.execute(query, params)
        log = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return log

    # =====================
    # Statistics Operations
    # =====================

    def get_stats(self) -> Dict[str, Any]:
        """Get overall statistics."""
        conn = self.get_connection()

        # Inventory items by org
        cursor = conn.execute('''
            SELECT org_key, COUNT(*) as total,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
            FROM inventory_items GROUP BY org_key
        ''')
        items_by_org = {row['org_key']: {
            'total': row['total'],
            'active': row['active'],
            'inactive': row['inactive']
        } for row in cursor.fetchall()}

        # Pricing coefficients by org
        cursor = conn.execute('''
            SELECT org_key, COUNT(*) as total,
                   SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as inactive
            FROM pricing_coefficients GROUP BY org_key
        ''')
        pricing_by_org = {row['org_key']: {
            'total': row['total'],
            'active': row['active'],
            'inactive': row['inactive']
        } for row in cursor.fetchall()}

        # Total counts
        cursor = conn.execute('SELECT COUNT(*) as total FROM inventory_items')
        total_items = cursor.fetchone()['total']

        cursor = conn.execute('SELECT COUNT(*) as total FROM pricing_coefficients')
        total_pricing = cursor.fetchone()['total']

        cursor = conn.execute('SELECT COUNT(*) as total FROM inventory_groups')
        total_inv_groups = cursor.fetchone()['total']

        cursor = conn.execute('SELECT COUNT(*) as total FROM pricing_groups')
        total_pricing_groups = cursor.fetchone()['total']

        conn.close()

        return {
            'total_inventory_items': total_items,
            'total_pricing_coefficients': total_pricing,
            'total_inventory_groups': total_inv_groups,
            'total_pricing_groups': total_pricing_groups,
            'inventory_by_org': items_by_org,
            'pricing_by_org': pricing_by_org
        }


# Singleton instance
inventory_db = InventoryDatabase()
