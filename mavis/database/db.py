import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from contextlib import contextmanager


def utc_now_iso() -> str:
    """Return current UTC time as ISO8601 string"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Database:
    """Database manager for Mavis's Unleashed data"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_dir = Path(__file__).parent
            db_path = db_dir / 'mavis.db'
        self.db_path = str(db_path)
        self.init_db()

    def init_db(self):
        """Initialize the database with schema and run migrations"""
        schema_path = Path(__file__).parent / 'schema.sql'
        with open(schema_path, 'r') as f:
            schema = f.read()

        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema)
        conn.commit()

        # Run migrations for existing databases
        self._run_migrations(conn)

        conn.close()

    def _run_migrations(self, conn):
        """Run database migrations to add missing columns to existing tables"""
        cursor = conn.cursor()

        # Check if is_sellable column exists, add if missing
        cursor.execute("PRAGMA table_info(unleashed_products)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'is_sellable' not in columns:
            cursor.execute("""
                ALTER TABLE unleashed_products
                ADD COLUMN is_sellable INTEGER DEFAULT 1
            """)
            conn.commit()

        if 'is_obsolete' not in columns:
            cursor.execute("""
                ALTER TABLE unleashed_products
                ADD COLUMN is_obsolete INTEGER DEFAULT 0
            """)
            conn.commit()

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
    # Product Operations
    # ─────────────────────────────────────────────────────────────

    def normalize_product_code(self, code: str) -> str:
        """Normalize a product code (trim and uppercase)"""
        if code is None:
            return ""
        return code.strip().upper()

    def upsert_product(self, product_data: Dict[str, Any]) -> tuple:
        """
        Insert or update a product.
        Returns (product_id, was_created) tuple.
        """
        code = self.normalize_product_code(product_data.get('product_code', ''))
        if not code:
            raise ValueError("Product code is required")

        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()

            # Check if product exists
            cursor.execute(
                "SELECT id, updated_at FROM unleashed_products WHERE product_code = ?",
                (code,)
            )
            existing = cursor.fetchone()

            if existing:
                # Update existing product
                cursor.execute("""
                    UPDATE unleashed_products SET
                        product_description = ?,
                        product_group = ?,
                        default_sell_price = ?,
                        sell_price_tier_9 = ?,
                        unit_of_measure = ?,
                        width = ?,
                        is_sellable = ?,
                        is_obsolete = ?,
                        raw_payload = ?,
                        updated_at = ?
                    WHERE product_code = ?
                """, (
                    product_data.get('product_description'),
                    product_data.get('product_group'),
                    product_data.get('default_sell_price'),
                    product_data.get('sell_price_tier_9'),
                    product_data.get('unit_of_measure'),
                    product_data.get('width'),
                    1 if product_data.get('is_sellable', True) else 0,
                    1 if product_data.get('is_obsolete', False) else 0,
                    product_data.get('raw_payload'),
                    now,
                    code
                ))
                return (existing['id'], False)
            else:
                # Insert new product
                cursor.execute("""
                    INSERT INTO unleashed_products (
                        product_code, product_description, product_group,
                        default_sell_price, sell_price_tier_9,
                        unit_of_measure, width, is_sellable, is_obsolete,
                        raw_payload, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    code,
                    product_data.get('product_description'),
                    product_data.get('product_group'),
                    product_data.get('default_sell_price'),
                    product_data.get('sell_price_tier_9'),
                    product_data.get('unit_of_measure'),
                    product_data.get('width'),
                    1 if product_data.get('is_sellable', True) else 0,
                    1 if product_data.get('is_obsolete', False) else 0,
                    product_data.get('raw_payload'),
                    now,
                    now
                ))
                return (cursor.lastrowid, True)

    def get_product_by_code(self, code: str) -> Optional[Dict]:
        """Get a product by its code"""
        code = self.normalize_product_code(code)
        if not code:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM unleashed_products WHERE product_code = ?",
            (code,)
        )
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def search_products(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search products by code or description.
        Returns products matching the query with a flag for valid fabric status.
        """
        if not query or len(query) < 2:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()
        search_term = f"%{query.upper()}%"
        cursor.execute("""
            SELECT *,
                CASE
                    WHEN LOWER(product_group) LIKE 'fabric%'
                        AND is_obsolete = 0
                        AND is_sellable = 1
                    THEN 1 ELSE 0
                END as is_valid_fabric
            FROM unleashed_products
            WHERE product_code LIKE ? OR product_description LIKE ?
            ORDER BY product_code
            LIMIT ?
        """, (search_term, search_term, limit))
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_products_by_codes(self, codes: List[str]) -> List[Dict]:
        """Get multiple products by their codes"""
        if not codes:
            return []

        normalized = [self.normalize_product_code(c) for c in codes if c]
        if not normalized:
            return []

        conn = self.get_connection()
        cursor = conn.cursor()

        placeholders = ','.join('?' * len(normalized))
        cursor.execute(
            f"SELECT * FROM unleashed_products WHERE product_code IN ({placeholders})",
            normalized
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_products_changed_since(self, timestamp: str) -> List[Dict]:
        """Get products updated since the given timestamp"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM unleashed_products WHERE updated_at >= ? ORDER BY updated_at",
            (timestamp,)
        )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_all_product_codes(self) -> List[str]:
        """Get all product codes in the database"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT product_code FROM unleashed_products")
        rows = cursor.fetchall()
        conn.close()

        return [row['product_code'] for row in rows]

    def get_product_count(self) -> int:
        """Get total number of products"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM unleashed_products")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_valid_fabric_products(self) -> List[Dict]:
        """
        Get all valid fabric products.

        Valid fabrics are products where:
        - product_group starts with 'Fabric' (case-insensitive)
        - is_obsolete = 0 (not obsolete)
        - is_sellable = 1 (sellable)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM unleashed_products
            WHERE LOWER(product_group) LIKE 'fabric%'
              AND is_obsolete = 0
              AND is_sellable = 1
            ORDER BY product_code
        """)
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_valid_fabric_codes(self) -> List[str]:
        """Get just the product codes for valid fabrics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT product_code FROM unleashed_products
            WHERE LOWER(product_group) LIKE 'fabric%'
              AND is_obsolete = 0
              AND is_sellable = 1
            ORDER BY product_code
        """)
        rows = cursor.fetchall()
        conn.close()

        return [row['product_code'] for row in rows]

    # ─────────────────────────────────────────────────────────────
    # Sync Metadata Operations
    # ─────────────────────────────────────────────────────────────

    def create_sync_record(self, sync_type: str) -> int:
        """Create a new sync record, returns the ID"""
        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_metadata (sync_type, status, started_at)
                VALUES (?, 'running', ?)
            """, (sync_type, now))
            return cursor.lastrowid

    def update_sync_record(
        self,
        sync_id: int,
        status: str,
        records_processed: int = 0,
        records_created: int = 0,
        records_updated: int = 0,
        error_message: str = None
    ):
        """Update a sync record with results"""
        now = utc_now_iso()

        with self.connection() as conn:
            cursor = conn.cursor()

            # Get started_at to calculate duration
            cursor.execute(
                "SELECT started_at FROM sync_metadata WHERE id = ?",
                (sync_id,)
            )
            row = cursor.fetchone()
            duration = None
            if row and row['started_at']:
                started = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
                finished = datetime.now(timezone.utc)
                duration = (finished - started).total_seconds()

            cursor.execute("""
                UPDATE sync_metadata SET
                    status = ?,
                    records_processed = ?,
                    records_created = ?,
                    records_updated = ?,
                    finished_at = ?,
                    duration_seconds = ?,
                    error_message = ?
                WHERE id = ?
            """, (
                status,
                records_processed,
                records_created,
                records_updated,
                now,
                duration,
                error_message,
                sync_id
            ))

    def update_sync_progress(
        self,
        sync_id: int,
        records_processed: int,
        records_created: int,
        records_updated: int
    ):
        """Update sync progress counts and elapsed time (for live updates)"""
        with self.connection() as conn:
            cursor = conn.cursor()

            # Get started_at to calculate elapsed duration
            cursor.execute(
                "SELECT started_at FROM sync_metadata WHERE id = ?",
                (sync_id,)
            )
            row = cursor.fetchone()
            duration = None
            if row and row['started_at']:
                started = datetime.fromisoformat(row['started_at'].replace('Z', '+00:00'))
                now = datetime.now(timezone.utc)
                duration = (now - started).total_seconds()

            cursor.execute("""
                UPDATE sync_metadata SET
                    records_processed = ?,
                    records_created = ?,
                    records_updated = ?,
                    duration_seconds = ?
                WHERE id = ?
            """, (
                records_processed,
                records_created,
                records_updated,
                duration,
                sync_id
            ))

    def get_last_successful_sync(self, sync_type: str) -> Optional[Dict]:
        """Get the most recent successful sync for a type"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM sync_metadata
            WHERE sync_type = ? AND status = 'success'
            ORDER BY finished_at DESC LIMIT 1
        """, (sync_type,))
        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def get_sync_history(self, sync_type: str = None, limit: int = 10) -> List[Dict]:
        """Get recent sync history"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if sync_type:
            cursor.execute("""
                SELECT * FROM sync_metadata
                WHERE sync_type = ?
                ORDER BY started_at DESC LIMIT ?
            """, (sync_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM sync_metadata
                ORDER BY started_at DESC LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def is_sync_running(self, sync_type: str) -> bool:
        """Check if a sync of the given type is currently running"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM sync_metadata
            WHERE sync_type = ? AND status = 'running'
        """, (sync_type,))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0


# Global database instance
db = Database()
