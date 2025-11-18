import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Any

class Database:
    """Database manager for Olive's offboarding workflows"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'olive.db'
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

    # Offboarding Requests
    def create_offboarding_request(self, data: Dict[str, Any], created_by: str = 'system') -> int:
        """Create a new offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO offboarding_requests (
                full_name, position, section, last_day,
                personal_email, phone_mobile, notes, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('full_name'),
            data.get('position', ''),
            data.get('section', ''),
            data.get('last_day'),
            data.get('personal_email', ''),
            data.get('phone_mobile', ''),
            data.get('notes', ''),
            created_by
        ))

        request_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Log the activity
        self.log_activity(request_id, 'request_created', 'Offboarding request created', created_by)

        return request_id

    def get_offboarding_request(self, request_id: int) -> Optional[Dict]:
        """Get an offboarding request by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM offboarding_requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_all_offboarding_requests(self, status: str = None) -> List[Dict]:
        """Get all offboarding requests, optionally filtered by status"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute(
                "SELECT * FROM offboarding_requests WHERE status = ? ORDER BY created_date DESC",
                (status,)
            )
        else:
            cursor.execute("SELECT * FROM offboarding_requests ORDER BY created_date DESC")

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_offboarding_status(self, request_id: int, status: str):
        """Update the status of an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = ["status = ?"]
        values = [status]

        if status == 'completed':
            updates.append("completed_date = CURRENT_TIMESTAMP")

        values.append(request_id)
        query = f"UPDATE offboarding_requests SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

        # Log the activity
        self.log_activity(request_id, f'status_changed_to_{status}', f'Status changed to {status}')

    def update_offboarding_results(self, request_id: int, **kwargs):
        """Update result fields for an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Build dynamic update query based on kwargs
        updates = []
        values = []
        for key, value in kwargs.items():
            if key in ['google_email', 'zendesk_user_id', 'peter_staff_id', 'wiki_username',
                      'buz_instances', 'had_google_access', 'had_zendesk_access',
                      'had_wiki_access', 'had_buz_access']:
                updates.append(f"{key} = ?")
                values.append(value)

        if updates:
            values.append(request_id)
            query = f"UPDATE offboarding_requests SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()

        conn.close()

    # Workflow Steps
    def create_workflow_steps(self, request_id: int, steps: List[Dict[str, Any]]):
        """Create workflow steps for an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        for step in steps:
            cursor.execute("""
                INSERT INTO workflow_steps (
                    offboarding_request_id, step_name, step_order,
                    requires_manual_action
                ) VALUES (?, ?, ?, ?)
            """, (
                request_id,
                step['name'],
                step['order'],
                step.get('requires_manual_action', False)
            ))

        conn.commit()
        conn.close()

    def get_workflow_steps(self, request_id: int) -> List[Dict]:
        """Get all workflow steps for an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM workflow_steps WHERE offboarding_request_id = ? ORDER BY step_order",
            (request_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_pending_manual_tasks(self) -> List[Dict]:
        """Get all workflow steps that require manual action and are pending"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ws.*, ofr.full_name, ofr.position
            FROM workflow_steps ws
            JOIN offboarding_requests ofr ON ws.offboarding_request_id = ofr.id
            WHERE ws.requires_manual_action = 1
            AND ws.status IN ('pending', 'in_progress')
            ORDER BY ws.started_date
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_workflow_step(self, step_id: int, status: str, success: bool = None,
                            result_data: Dict = None, error_message: str = None,
                            zendesk_ticket_id: str = None):
        """Update a workflow step"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Prepare the update
        updates = ["status = ?"]
        values = [status]

        # Check if started_date needs to be set
        cursor.execute("SELECT started_date FROM workflow_steps WHERE id = ?", (step_id,))
        row = cursor.fetchone()
        if status == 'in_progress' and (not row or not row[0]):
            updates.append("started_date = CURRENT_TIMESTAMP")

        if status in ['completed', 'failed', 'skipped']:
            updates.append("completed_date = CURRENT_TIMESTAMP")

        if success is not None:
            updates.append("success = ?")
            values.append(success)

        if result_data:
            updates.append("result_data = ?")
            values.append(json.dumps(result_data))

        if error_message:
            updates.append("error_message = ?")
            values.append(error_message)

        if zendesk_ticket_id:
            updates.append("zendesk_ticket_id = ?")
            values.append(zendesk_ticket_id)

        values.append(step_id)
        query = f"UPDATE workflow_steps SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, values)
        conn.commit()
        conn.close()

    # Activity Log
    def log_activity(self, request_id: int, activity_type: str, description: str,
                    created_by: str = 'system', metadata: Dict = None):
        """Log an activity for an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO activity_log (
                offboarding_request_id, activity_type, description,
                created_by, metadata
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            request_id,
            activity_type,
            description,
            created_by,
            json.dumps(metadata) if metadata else None
        ))

        conn.commit()
        conn.close()

    def get_activity_log(self, request_id: int) -> List[Dict]:
        """Get activity log for an offboarding request"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM activity_log WHERE offboarding_request_id = ? ORDER BY created_date DESC",
            (request_id,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

# Global database instance
db = Database()
