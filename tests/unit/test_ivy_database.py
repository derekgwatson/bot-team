"""
Unit tests for Ivy database operations.
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
os.environ['FLASK_SECRET_KEY'] = 'test-secret-key'
os.environ['BUZ_ORGS'] = ''  # Empty for tests - no actual Buz auth needed

# Add ivy to path before importing its modules
sys.path.insert(0, str(project_root / 'ivy'))

# Clear any cached config module
if 'config' in sys.modules:
    del sys.modules['config']

# Import Database directly using importlib to avoid sys.modules caching issues
module_path = project_root / 'ivy' / 'database' / 'db.py'
spec = importlib.util.spec_from_file_location('ivy_database_db', module_path)
ivy_db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ivy_db_module)
InventoryDatabase = ivy_db_module.InventoryDatabase


@pytest.fixture
def ivy_db(tmp_path):
    """Create an isolated Ivy database for testing."""
    db_path = tmp_path / "ivy_test.db"
    return InventoryDatabase(str(db_path))


@pytest.mark.unit
@pytest.mark.ivy
class TestInventoryItemOperations:
    """Test inventory item CRUD operations."""

    def test_upsert_inventory_item_new(self, ivy_db):
        """Test inserting a new inventory item."""
        result = ivy_db.upsert_inventory_item(
            org_key='canberra',
            group_code='ROLL',
            item_code='ROLL001',
            item_name='Roller Blind Standard',
            description='Standard roller blind',
            is_active=True,
            cost_price=50.00,
            sell_price=99.00
        )

        assert result['success'] is True
        assert result['action'] == 'created'

        # Verify item exists
        item = ivy_db.get_inventory_item('canberra', 'ROLL', 'ROLL001')
        assert item is not None
        assert item['item_name'] == 'Roller Blind Standard'
        assert item['cost_price'] == 50.00

    def test_upsert_inventory_item_update(self, ivy_db):
        """Test updating an existing inventory item."""
        # Create item first
        ivy_db.upsert_inventory_item(
            org_key='canberra',
            group_code='ROLL',
            item_code='ROLL001',
            item_name='Old Name',
            cost_price=50.00
        )

        # Update item
        result = ivy_db.upsert_inventory_item(
            org_key='canberra',
            group_code='ROLL',
            item_code='ROLL001',
            item_name='New Name',
            cost_price=60.00
        )

        assert result['success'] is True
        assert result['action'] == 'updated'

        # Verify update
        item = ivy_db.get_inventory_item('canberra', 'ROLL', 'ROLL001')
        assert item['item_name'] == 'New Name'
        assert item['cost_price'] == 60.00

    def test_bulk_upsert_inventory_items(self, ivy_db):
        """Test bulk upserting inventory items."""
        items = [
            {'group_code': 'ROLL', 'item_code': 'ROLL001', 'item_name': 'Item 1', 'is_active': True},
            {'group_code': 'ROLL', 'item_code': 'ROLL002', 'item_name': 'Item 2', 'is_active': True},
            {'group_code': 'VERT', 'item_code': 'VERT001', 'item_name': 'Item 3', 'is_active': False},
        ]

        result = ivy_db.bulk_upsert_inventory_items('canberra', items)

        assert result['success'] is True
        assert result['created'] == 3
        assert result['updated'] == 0
        assert result['total'] == 3

        # Verify all items exist
        all_items = ivy_db.get_inventory_items(org_key='canberra')
        assert len(all_items) == 3

    def test_get_inventory_items_with_filters(self, ivy_db):
        """Test filtering inventory items."""
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R1', item_name='Active Roller', is_active=True)
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R2', item_name='Inactive Roller', is_active=False)
        ivy_db.upsert_inventory_item(org_key='tweed', group_code='VERT', item_code='V1', item_name='Vertical', is_active=True)

        # Filter by org
        canberra_items = ivy_db.get_inventory_items(org_key='canberra')
        assert len(canberra_items) == 2

        # Filter by group
        roll_items = ivy_db.get_inventory_items(group_code='ROLL')
        assert len(roll_items) == 2

        # Filter by active status
        active_items = ivy_db.get_inventory_items(is_active=True)
        assert len(active_items) == 2

        # Search
        roller_items = ivy_db.get_inventory_items(search='Roller')
        assert len(roller_items) == 2

    def test_get_inventory_item_count(self, ivy_db):
        """Test counting inventory items."""
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R1', item_name='Item 1', is_active=True)
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R2', item_name='Item 2', is_active=False)

        total = ivy_db.get_inventory_item_count()
        assert total == 2

        active = ivy_db.get_inventory_item_count(is_active=True)
        assert active == 1


@pytest.mark.unit
@pytest.mark.ivy
class TestInventoryGroupOperations:
    """Test inventory group operations."""

    def test_upsert_inventory_group(self, ivy_db):
        """Test inserting/updating inventory groups."""
        result = ivy_db.upsert_inventory_group(
            org_key='canberra',
            group_code='ROLL',
            group_name='Roller Blinds',
            item_count=50
        )

        assert result['success'] is True
        assert result['action'] == 'created'

        groups = ivy_db.get_inventory_groups('canberra')
        assert len(groups) == 1
        assert groups[0]['group_code'] == 'ROLL'
        assert groups[0]['item_count'] == 50


@pytest.mark.unit
@pytest.mark.ivy
class TestPricingCoefficientOperations:
    """Test pricing coefficient CRUD operations."""

    def test_upsert_pricing_coefficient_new(self, ivy_db):
        """Test inserting a new pricing coefficient."""
        result = ivy_db.upsert_pricing_coefficient(
            org_key='canberra',
            group_code='ROLL',
            coefficient_code='WIDTH_MULT',
            coefficient_name='Width Multiplier',
            base_value=1.25,
            is_active=True
        )

        assert result['success'] is True
        assert result['action'] == 'created'

        # Verify coefficient exists
        coeff = ivy_db.get_pricing_coefficient('canberra', 'ROLL', 'WIDTH_MULT')
        assert coeff is not None
        assert coeff['coefficient_name'] == 'Width Multiplier'
        assert coeff['base_value'] == 1.25

    def test_bulk_upsert_pricing_coefficients(self, ivy_db):
        """Test bulk upserting pricing coefficients."""
        coefficients = [
            {'group_code': 'ROLL', 'coefficient_code': 'C1', 'coefficient_name': 'Coeff 1', 'base_value': 1.0},
            {'group_code': 'ROLL', 'coefficient_code': 'C2', 'coefficient_name': 'Coeff 2', 'base_value': 1.5},
            {'group_code': 'VERT', 'coefficient_code': 'C3', 'coefficient_name': 'Coeff 3', 'base_value': 2.0},
        ]

        result = ivy_db.bulk_upsert_pricing_coefficients('canberra', coefficients)

        assert result['success'] is True
        assert result['created'] == 3

        # Verify all exist
        all_coeffs = ivy_db.get_pricing_coefficients(org_key='canberra')
        assert len(all_coeffs) == 3

    def test_get_pricing_coefficients_with_filters(self, ivy_db):
        """Test filtering pricing coefficients."""
        ivy_db.upsert_pricing_coefficient(org_key='canberra', group_code='ROLL', coefficient_code='C1', coefficient_name='Active', is_active=True, base_value=1.0)
        ivy_db.upsert_pricing_coefficient(org_key='canberra', group_code='ROLL', coefficient_code='C2', coefficient_name='Inactive', is_active=False, base_value=1.0)
        ivy_db.upsert_pricing_coefficient(org_key='tweed', group_code='VERT', coefficient_code='C3', coefficient_name='Other', is_active=True, base_value=1.0)

        # Filter by org
        canberra = ivy_db.get_pricing_coefficients(org_key='canberra')
        assert len(canberra) == 2

        # Filter by active
        active = ivy_db.get_pricing_coefficients(is_active=True)
        assert len(active) == 2


@pytest.mark.unit
@pytest.mark.ivy
class TestPricingGroupOperations:
    """Test pricing group operations."""

    def test_upsert_pricing_group(self, ivy_db):
        """Test inserting/updating pricing groups."""
        result = ivy_db.upsert_pricing_group(
            org_key='canberra',
            group_code='ROLL',
            group_name='Roller Blinds Pricing',
            coefficient_count=25
        )

        assert result['success'] is True

        groups = ivy_db.get_pricing_groups('canberra')
        assert len(groups) == 1
        assert groups[0]['coefficient_count'] == 25


@pytest.mark.unit
@pytest.mark.ivy
class TestSyncLogOperations:
    """Test sync log operations."""

    def test_start_and_complete_sync(self, ivy_db):
        """Test starting and completing a sync."""
        sync_id = ivy_db.start_sync('canberra', 'inventory')
        assert sync_id is not None

        # Verify it shows as running
        running = ivy_db.get_running_syncs('canberra')
        assert len(running) == 1

        # Complete the sync
        ivy_db.complete_sync(sync_id, item_count=100, status='success', duration_seconds=15.5)

        # Should no longer be running
        running = ivy_db.get_running_syncs('canberra')
        assert len(running) == 0

        # Check last sync
        last = ivy_db.get_last_sync('canberra', 'inventory')
        assert last is not None
        assert last['item_count'] == 100
        assert last['status'] == 'success'

    def test_sync_history(self, ivy_db):
        """Test getting sync history."""
        # Create some syncs
        sync_id = ivy_db.start_sync('canberra', 'inventory')
        ivy_db.complete_sync(sync_id, 50, 'success', '', 10)

        sync_id = ivy_db.start_sync('canberra', 'pricing')
        ivy_db.complete_sync(sync_id, 25, 'success', '', 5)

        sync_id = ivy_db.start_sync('tweed', 'inventory')
        ivy_db.complete_sync(sync_id, 30, 'failed', 'Auth error', 0)

        # Get all history
        history = ivy_db.get_sync_history()
        assert len(history) == 3

        # Filter by org
        canberra_history = ivy_db.get_sync_history(org_key='canberra')
        assert len(canberra_history) == 2

        # Filter by type
        inventory_history = ivy_db.get_sync_history(sync_type='inventory')
        assert len(inventory_history) == 2


@pytest.mark.unit
@pytest.mark.ivy
class TestActivityLogOperations:
    """Test activity log operations."""

    def test_log_activity(self, ivy_db):
        """Test logging an activity."""
        log_id = ivy_db.log_activity(
            action='sync_inventory',
            entity_type='inventory',
            entity_id='canberra',
            org_key='canberra',
            new_value='100 items synced',
            performed_by='admin@example.com'
        )

        assert log_id is not None

        log = ivy_db.get_activity_log(org_key='canberra')
        assert len(log) == 1
        assert log[0]['action'] == 'sync_inventory'

    def test_activity_log_filters(self, ivy_db):
        """Test filtering activity log."""
        ivy_db.log_activity(action='sync', entity_type='inventory', entity_id='test', org_key='canberra', new_value='test')
        ivy_db.log_activity(action='sync', entity_type='pricing', entity_id='test', org_key='canberra', new_value='test')
        ivy_db.log_activity(action='sync', entity_type='inventory', entity_id='test', org_key='tweed', new_value='test')

        # Filter by org
        canberra = ivy_db.get_activity_log(org_key='canberra')
        assert len(canberra) == 2

        # Filter by entity_type
        inventory = ivy_db.get_activity_log(entity_type='inventory')
        assert len(inventory) == 2


@pytest.mark.unit
@pytest.mark.ivy
class TestStatsOperations:
    """Test statistics operations."""

    def test_get_stats(self, ivy_db):
        """Test getting overall statistics."""
        # Add some data
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R1', item_name='Item 1', is_active=True)
        ivy_db.upsert_inventory_item(org_key='canberra', group_code='ROLL', item_code='R2', item_name='Item 2', is_active=False)
        ivy_db.upsert_inventory_item(org_key='tweed', group_code='VERT', item_code='V1', item_name='Item 3', is_active=True)

        ivy_db.upsert_pricing_coefficient(org_key='canberra', group_code='ROLL', coefficient_code='C1', coefficient_name='Coeff 1', base_value=1.0)
        ivy_db.upsert_pricing_coefficient(org_key='canberra', group_code='ROLL', coefficient_code='C2', coefficient_name='Coeff 2', base_value=1.0)

        ivy_db.upsert_inventory_group(org_key='canberra', group_code='ROLL', group_name='Rollers')
        ivy_db.upsert_pricing_group(org_key='canberra', group_code='ROLL', group_name='Rollers Pricing')

        stats = ivy_db.get_stats()

        assert stats['total_inventory_items'] == 3
        assert stats['total_pricing_coefficients'] == 2
        assert stats['total_inventory_groups'] == 1
        assert stats['total_pricing_groups'] == 1

        assert 'canberra' in stats['inventory_by_org']
        assert stats['inventory_by_org']['canberra']['total'] == 2
        assert stats['inventory_by_org']['canberra']['active'] == 1
