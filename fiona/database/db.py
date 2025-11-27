import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from contextlib import contextmanager
from shared.migrations import MigrationRunner


def utc_now_iso() -> str:
    """Return current UTC time as ISO8601 string"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    """Database manager for Fiona's fabric descriptions"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'fiona.db'
        self.db_path = str(db_path)
        self._run_migrations()

    def _run_migrations(self):
        """Run database migrations"""
        migrations_dir = Path(__file__).parent.parent / 'migrations'
        runner = MigrationRunner(
            db_path=self.db_path,
            migrations_dir=str(migrations_dir)
        )
        runner.run_pending_migrations(verbose=True)

    def get_connection(self):
        """Get a database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def connection(self):
        """Context manager for database connections"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ─────────────────────────────────────────────────────────────
    # Fabric Description Operations
    # ─────────────────────────────────────────────────────────────

    def normalize_product_code(self, code: str) -> str:
        """Normalize a product code (trim and uppercase)"""
        if code is None:
            return ""
        return code.strip().upper()

    def get_fabric_by_code(self, code: str) -> Optional[Dict]:
        """Get a fabric description by product code"""
        code = self.normalize_product_code(code)
        if not code:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM fabric_descriptions WHERE product_code = ?",
            (code,)
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_fabrics_by_codes(self, codes: List[str]) -> List[Dict]:
        """Get multiple fabric descriptions by their codes"""
        if not codes:
            return []

        normalized = [self.normalize_product_code(c) for c in codes if c]
        if not normalized:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        placeholders = ','.join('?' * len(normalized))
        cursor.execute(
            f"SELECT * FROM fabric_descriptions WHERE product_code IN ({placeholders})",
            normalized
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def upsert_fabric(self, fabric_data: Dict[str, Any], updated_by: str = None) -> tuple:
        """
        Insert or update a fabric description.
        Returns (fabric_id, was_created) tuple.
        """
        code = self.normalize_product_code(fabric_data.get('product_code', ''))
        if not code:
            raise ValueError("Product code is required")

        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()

            # Check if fabric exists
            cursor.execute(
                "SELECT id FROM fabric_descriptions WHERE product_code = ?",
                (code,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing fabric
                cursor.execute("""
                    UPDATE fabric_descriptions SET
                        supplier_material = ?,
                        supplier_material_type = ?,
                        supplier_colour = ?,
                        watson_material = ?,
                        watson_colour = ?,
                        fabric_type = ?,
                        updated_at = ?,
                        updated_by = ?
                    WHERE product_code = ?
                """, (
                    fabric_data.get('supplier_material'),
                    fabric_data.get('supplier_material_type'),
                    fabric_data.get('supplier_colour'),
                    fabric_data.get('watson_material'),
                    fabric_data.get('watson_colour'),
                    fabric_data.get('fabric_type'),
                    now,
                    updated_by,
                    code
                ))
                return (existing['id'], False)
            else:
                # Insert new fabric
                cursor.execute("""
                    INSERT INTO fabric_descriptions (
                        product_code,
                        supplier_material, supplier_material_type, supplier_colour,
                        watson_material, watson_colour, fabric_type,
                        created_at, updated_at, updated_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    fabric_data.get('supplier_material'),
                    fabric_data.get('supplier_material_type'),
                    fabric_data.get('supplier_colour'),
                    fabric_data.get('watson_material'),
                    fabric_data.get('watson_colour'),
                    fabric_data.get('fabric_type'),
                    now,
                    now,
                    updated_by
                ))
                return (cursor.lastrowid, True)

    def delete_fabric(self, code: str) -> bool:
        """Delete a fabric description by product code. Returns True if deleted."""
        code = self.normalize_product_code(code)
        if not code:
            return False

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM fabric_descriptions WHERE product_code = ?",
                (code,)
            )
            return cursor.rowcount > 0

    def get_all_fabrics(self, limit: int = 1000, offset: int = 0) -> List[Dict]:
        """Get all fabric descriptions with pagination"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM fabric_descriptions
               ORDER BY product_code
               LIMIT ? OFFSET ?""",
            (limit, offset)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def search_fabrics(
        self,
        query: str = None,
        supplier_material: str = None,
        watson_material: str = None,
        fabric_type: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Search fabric descriptions.

        Args:
            query: General search term (searches product_code and all name fields)
            supplier_material: Filter by supplier material
            watson_material: Filter by watson material
            fabric_type: Filter by fabric type (exact match)
            limit: Max results to return
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if query:
            conditions.append("""(
                product_code LIKE ? OR
                supplier_material LIKE ? OR
                supplier_material_type LIKE ? OR
                supplier_colour LIKE ? OR
                watson_material LIKE ? OR
                watson_colour LIKE ?
            )""")
            like_query = f"%{query}%"
            params.extend([like_query] * 6)

        if supplier_material:
            conditions.append("supplier_material LIKE ?")
            params.append(f"%{supplier_material}%")

        if watson_material:
            conditions.append("watson_material LIKE ?")
            params.append(f"%{watson_material}%")

        if fabric_type:
            conditions.append("fabric_type = ?")
            params.append(fabric_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        cursor.execute(
            f"""SELECT * FROM fabric_descriptions
                WHERE {where_clause}
                ORDER BY product_code
                LIMIT ?""",
            params + [limit]
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_fabric_count(self) -> int:
        """Get total number of fabric descriptions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fabric_descriptions")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_all_product_codes(self) -> List[str]:
        """Get all product codes that have descriptions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT product_code FROM fabric_descriptions ORDER BY product_code")
        rows = cursor.fetchall()
        conn.close()
        return [row['product_code'] for row in rows]

    def bulk_upsert_fabrics(self, fabrics: List[Dict], updated_by: str = None) -> Dict:
        """
        Bulk insert/update fabric descriptions.
        Returns stats about the operation.
        """
        created = 0
        updated = 0
        errors = []

        for fabric in fabrics:
            try:
                _, was_created = self.upsert_fabric(fabric, updated_by)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                errors.append({
                    'product_code': fabric.get('product_code'),
                    'error': str(e)
                })

        return {
            'total': len(fabrics),
            'created': created,
            'updated': updated,
            'errors': errors
        }

    def get_distinct_fabric_types(self) -> List[str]:
        """Get all distinct fabric types (non-null) for filter dropdowns."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT fabric_type
            FROM fabric_descriptions
            WHERE fabric_type IS NOT NULL AND fabric_type != ''
            ORDER BY fabric_type
        """)
        rows = cursor.fetchall()
        conn.close()
        return [row['fabric_type'] for row in rows]

    def update_fabric_type(self, code: str, fabric_type: str) -> bool:
        """
        Update just the fabric_type for an existing fabric.
        Returns True if updated, False if not found.
        """
        code = self.normalize_product_code(code)
        if not code:
            return False

        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE fabric_descriptions
                SET fabric_type = ?, updated_at = ?
                WHERE product_code = ?
            """, (fabric_type, now, code))
            return cursor.rowcount > 0

    def bulk_update_fabric_types(self, type_mapping: Dict[str, str]) -> Dict:
        """
        Bulk update fabric types for multiple product codes.

        Args:
            type_mapping: Dict of {product_code: fabric_type}

        Returns:
            {'updated': int, 'not_found': int, 'errors': [...]}
        """
        updated = 0
        not_found = 0
        errors = []

        for code, fabric_type in type_mapping.items():
            try:
                if self.update_fabric_type(code, fabric_type):
                    updated += 1
                else:
                    not_found += 1
            except Exception as e:
                errors.append({'code': code, 'error': str(e)})

        return {
            'updated': updated,
            'not_found': not_found,
            'errors': errors if errors else None
        }

    def get_fabrics_by_type(self, fabric_type: str, limit: int = 10000) -> List[Dict]:
        """Get all fabrics of a specific type."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM fabric_descriptions
               WHERE fabric_type = ?
               ORDER BY product_code
               LIMIT ?""",
            (fabric_type, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]


# Global database instance
db = Database()
