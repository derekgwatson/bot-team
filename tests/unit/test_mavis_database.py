"""
Unit tests for Mavis database operations.
"""

import os
import sys
import pytest
import importlib.util
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['UNLEASHED_API_ID'] = 'test-api-id'
os.environ['UNLEASHED_API_KEY'] = 'test-api-key'

# Import Database directly using importlib to avoid sys.modules caching issues
# that can cause the wrong database.db module to be loaded
module_path = project_root / 'mavis' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('mavis_database_db', module_path)
mavis_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mavis_db_module)
MavisDatabase = mavis_db_module.Database


@pytest.fixture
def mavis_db(tmp_path):
    """Create an isolated Mavis database for testing."""
    db_path = tmp_path / "mavis_test.db"
    return MavisDatabase(str(db_path))


@pytest.mark.unit
@pytest.mark.mavis
class TestProductOperations:
    """Test product CRUD operations."""

    def test_normalize_product_code(self, mavis_db):
        """Test product code normalization."""
        assert mavis_db.normalize_product_code("  fab123  ") == "FAB123"
        assert mavis_db.normalize_product_code("ABC-456") == "ABC-456"
        assert mavis_db.normalize_product_code(None) == ""
        assert mavis_db.normalize_product_code("") == ""

    def test_upsert_product_create(self, mavis_db):
        """Test inserting a new product."""
        product_data = {
            'product_code': 'TEST001',
            'product_description': 'Test Product',
            'product_group': 'Test Group',
            'default_sell_price': 99.99,
            'sell_price_tier_9': 89.99,
            'unit_of_measure': 'EACH',
            'width': 2.5,
            'raw_payload': '{"test": "data"}'
        }

        product_id, was_created = mavis_db.upsert_product(product_data)

        assert product_id is not None
        assert was_created is True

        # Verify the product was stored correctly
        product = mavis_db.get_product_by_code('TEST001')
        assert product is not None
        assert product['product_code'] == 'TEST001'
        assert product['product_description'] == 'Test Product'
        assert product['product_group'] == 'Test Group'
        assert product['default_sell_price'] == 99.99
        assert product['sell_price_tier_9'] == 89.99

    def test_upsert_product_update(self, mavis_db):
        """Test updating an existing product."""
        # Create initial product
        initial_data = {
            'product_code': 'TEST002',
            'product_description': 'Initial Description',
            'default_sell_price': 100.00
        }
        product_id1, was_created1 = mavis_db.upsert_product(initial_data)
        assert was_created1 is True

        # Update the product
        updated_data = {
            'product_code': 'TEST002',
            'product_description': 'Updated Description',
            'default_sell_price': 150.00
        }
        product_id2, was_created2 = mavis_db.upsert_product(updated_data)

        assert was_created2 is False
        assert product_id1 == product_id2

        # Verify the update
        product = mavis_db.get_product_by_code('TEST002')
        assert product['product_description'] == 'Updated Description'
        assert product['default_sell_price'] == 150.00

    def test_upsert_product_case_insensitive(self, mavis_db):
        """Test that product codes are normalized to uppercase."""
        product_data = {
            'product_code': 'lowercase123',
            'product_description': 'Test'
        }

        mavis_db.upsert_product(product_data)

        # Should be able to find by uppercase
        product = mavis_db.get_product_by_code('LOWERCASE123')
        assert product is not None

        # Should also find by lowercase
        product = mavis_db.get_product_by_code('lowercase123')
        assert product is not None

    def test_get_product_by_code_not_found(self, mavis_db):
        """Test getting a non-existent product."""
        product = mavis_db.get_product_by_code('NONEXISTENT')
        assert product is None

    def test_get_products_by_codes(self, mavis_db):
        """Test bulk product lookup."""
        # Create some products
        for i in range(3):
            mavis_db.upsert_product({
                'product_code': f'BULK{i:03d}',
                'product_description': f'Bulk Product {i}'
            })

        # Lookup by codes
        products = mavis_db.get_products_by_codes(['BULK000', 'BULK001', 'BULK002', 'NOTFOUND'])

        assert len(products) == 3
        codes = {p['product_code'] for p in products}
        assert codes == {'BULK000', 'BULK001', 'BULK002'}

    def test_get_products_by_codes_empty(self, mavis_db):
        """Test bulk lookup with empty list."""
        products = mavis_db.get_products_by_codes([])
        assert products == []

    def test_get_product_count(self, mavis_db):
        """Test product count."""
        assert mavis_db.get_product_count() == 0

        mavis_db.upsert_product({'product_code': 'COUNT001'})
        assert mavis_db.get_product_count() == 1

        mavis_db.upsert_product({'product_code': 'COUNT002'})
        assert mavis_db.get_product_count() == 2


@pytest.mark.unit
@pytest.mark.mavis
class TestSyncMetadataOperations:
    """Test sync metadata operations."""

    def test_create_sync_record(self, mavis_db):
        """Test creating a sync record."""
        sync_id = mavis_db.create_sync_record('products')

        assert sync_id is not None
        assert sync_id > 0

    def test_update_sync_record_success(self, mavis_db):
        """Test updating sync record with success."""
        sync_id = mavis_db.create_sync_record('products')

        mavis_db.update_sync_record(
            sync_id,
            status='success',
            records_processed=100,
            records_created=50,
            records_updated=50
        )

        last_sync = mavis_db.get_last_successful_sync('products')
        assert last_sync is not None
        assert last_sync['status'] == 'success'
        assert last_sync['records_processed'] == 100

    def test_update_sync_record_failure(self, mavis_db):
        """Test updating sync record with failure."""
        sync_id = mavis_db.create_sync_record('products')

        mavis_db.update_sync_record(
            sync_id,
            status='failed',
            error_message='Connection timeout'
        )

        # Should not appear as last successful
        last_sync = mavis_db.get_last_successful_sync('products')
        assert last_sync is None

    def test_get_sync_history(self, mavis_db):
        """Test getting sync history."""
        # Create multiple sync records
        for i in range(5):
            sync_id = mavis_db.create_sync_record('products')
            mavis_db.update_sync_record(sync_id, status='success')

        history = mavis_db.get_sync_history('products', limit=3)
        assert len(history) == 3

    def test_is_sync_running(self, mavis_db):
        """Test checking if sync is running."""
        assert mavis_db.is_sync_running('products') is False

        sync_id = mavis_db.create_sync_record('products')
        assert mavis_db.is_sync_running('products') is True

        mavis_db.update_sync_record(sync_id, status='success')
        assert mavis_db.is_sync_running('products') is False
