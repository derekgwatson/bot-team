import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any


class Database:
    """Database manager for Fred's pending operations"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'fred.db'
        self.db_path = str(db_path)
        self.init_db()

    def init_db(self):
        """Initialize the database with schema"""
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r') as f:
            schema = f.read()

        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.commit()
        conn.close()

    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Pending Operations
    def queue_operation(self, operation_type: str, operation_data: Dict[str, Any],
                        created_by: str = 'system', external_reference: str = None) -> int:
        """Queue a new operation for later execution"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Extract target email and name for easy lookup
        target_email = operation_data.get('email', '')
        target_name = operation_data.get('name', operation_data.get('first_name', ''))
        if operation_data.get('last_name'):
            target_name = f"{target_name} {operation_data.get('last_name')}"

        cursor.execute("""
            INSERT INTO pending_operations (
                operation_type, operation_data, target_email, target_name,
                created_by, external_reference
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            operation_type,
            json.dumps(operation_data),
            target_email,
            target_name.strip(),
            created_by,
            external_reference
        ))

        operation_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return operation_id

    def get_operation(self, operation_id: int) -> Optional[Dict]:
        """Get a pending operation by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM pending_operations WHERE id = ?", (operation_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            result = dict(row)
            # Parse JSON fields
            if result.get('operation_data'):
                result['operation_data'] = json.loads(result['operation_data'])
            if result.get('result_data'):
                result['result_data'] = json.loads(result['result_data'])
            return result
        return None

    def get_operations(self, status: str = None, operation_type: str = None,
                       limit: int = 100) -> List[Dict]:
        """Get operations, optionally filtered by status and/or type"""
        conn = self.get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM pending_operations WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if operation_type:
            query += " AND operation_type = ?"
            params.append(operation_type)

        query += " ORDER BY created_date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            if result.get('operation_data'):
                result['operation_data'] = json.loads(result['operation_data'])
            if result.get('result_data'):
                result['result_data'] = json.loads(result['result_data'])
            results.append(result)

        return results

    def get_pending_operations(self) -> List[Dict]:
        """Get all pending operations"""
        return self.get_operations(status='pending')

    def update_operation_status(self, operation_id: int, status: str,
                                 result_data: Dict = None, error_message: str = None,
                                 executed_by: str = None):
        """Update operation status and results"""
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = ["status = ?"]
        values = [status]

        if status in ['completed', 'failed']:
            updates.append("executed_date = CURRENT_TIMESTAMP")

        if executed_by:
            updates.append("executed_by = ?")
            values.append(executed_by)

        if result_data:
            updates.append("result_data = ?")
            values.append(json.dumps(result_data))

        if error_message:
            updates.append("error_message = ?")
            values.append(error_message)

        values.append(operation_id)
        query = f"UPDATE pending_operations SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    def cancel_operation(self, operation_id: int, cancelled_by: str = 'system'):
        """Cancel a pending operation"""
        self.update_operation_status(operation_id, 'cancelled', executed_by=cancelled_by)

    def delete_operation(self, operation_id: int):
        """Delete an operation (for cleanup)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_operations WHERE id = ?", (operation_id,))
        conn.commit()
        conn.close()

    def get_operations_by_external_ref(self, external_reference: str) -> List[Dict]:
        """Get operations by external reference (e.g., Oscar request ID)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pending_operations WHERE external_reference = ? ORDER BY created_date",
            (external_reference,)
        )
        rows = cursor.fetchall()
        conn.close()

        results = []
        for row in rows:
            result = dict(row)
            if result.get('operation_data'):
                result['operation_data'] = json.loads(result['operation_data'])
            if result.get('result_data'):
                result['result_data'] = json.loads(result['result_data'])
            results.append(result)

        return results


# Global database instance
db = Database()
