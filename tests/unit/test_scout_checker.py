"""
Unit tests for Scout checker service.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'


@pytest.fixture
def scout_db(tmp_path):
    """Create an isolated Scout database for testing."""
    db_path = tmp_path / "scout_test.db"

    sys.path.insert(0, str(project_root / 'scout'))
    from database.db import ScoutDatabase

    return ScoutDatabase(str(db_path))


@pytest.fixture
def mock_mavis_client():
    """Mock Mavis client."""
    mock = MagicMock()

    # Default return values
    mock.get_valid_fabrics.return_value = {
        'codes': ['FAB001', 'FAB002', 'FAB003', 'FAB004'],
        'count': 4
    }

    mock.get_sync_status.return_value = {
        'status': 'idle',
        'last_successful_sync_at': '2025-01-15T10:00:00Z',
        'last_error': None
    }

    mock.check_connection.return_value = {
        'connected': True,
        'status': 'healthy'
    }

    return mock


@pytest.fixture
def mock_fiona_client():
    """Mock Fiona client."""
    mock = MagicMock()

    # Return fabrics that exist (some will be missing from Mavis)
    mock.get_all_fabric_codes.return_value = {'FAB001', 'FAB002', 'OLD001'}

    mock.get_all_fabrics.return_value = {
        'fabrics': [
            {
                'product_code': 'FAB001',
                'supplier_material': 'Blockout',
                'supplier_colour': 'White'
            },
            {
                'product_code': 'FAB002',
                'supplier_material': None,  # Incomplete
                'supplier_colour': 'Black'
            },
            {
                'product_code': 'OLD001',
                'supplier_material': 'Old Material',
                'supplier_colour': None  # Incomplete
            }
        ],
        'count': 3,
        'total': 3
    }

    mock.check_connection.return_value = {
        'connected': True,
        'status': 'healthy'
    }

    return mock


@pytest.fixture
def mock_sadie_client():
    """Mock Sadie client."""
    mock = MagicMock()

    mock.create_ticket.return_value = {
        'ticket_id': 12345,
        'url': 'https://zendesk.com/tickets/12345',
        'status': 'new'
    }

    mock.check_connection.return_value = {
        'connected': True,
        'status': 'healthy'
    }

    return mock


@pytest.mark.unit
@pytest.mark.scout
class TestCheckerMissingDescriptions:
    """Test missing descriptions check."""

    def test_detects_missing_descriptions(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that missing descriptions are detected."""
        sys.path.insert(0, str(project_root / 'scout'))

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_missing_descriptions()

            # FAB003 and FAB004 are in Mavis but not Fiona
            assert result['issues_found'] == 2
            assert result['tickets_created'] == 1
            assert 'FAB003' in result['details']['missing_codes']
            assert 'FAB004' in result['details']['missing_codes']

    def test_no_ticket_if_already_reported(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that no duplicate ticket is created."""
        sys.path.insert(0, str(project_root / 'scout'))

        # Pre-record the issue
        scout_db.record_issue(
            issue_type='missing_description',
            issue_key='batch',
            ticket_id=99999
        )

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_missing_descriptions()

            # Issues found but no new ticket
            assert result['issues_found'] == 2
            assert result['tickets_created'] == 0
            mock_sadie_client.create_ticket.assert_not_called()


@pytest.mark.unit
@pytest.mark.scout
class TestCheckerObsoleteFabrics:
    """Test obsolete fabrics check."""

    def test_detects_obsolete_fabrics(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that obsolete fabrics are detected."""
        sys.path.insert(0, str(project_root / 'scout'))

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_obsolete_fabrics()

            # OLD001 is in Fiona but not in Mavis valid fabrics
            assert result['issues_found'] == 1
            assert result['tickets_created'] == 1
            assert 'OLD001' in result['details']['obsolete_codes']


@pytest.mark.unit
@pytest.mark.scout
class TestCheckerIncompleteDescriptions:
    """Test incomplete descriptions check."""

    def test_detects_incomplete_descriptions(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that incomplete descriptions are detected."""
        sys.path.insert(0, str(project_root / 'scout'))

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_incomplete_descriptions()

            # FAB002 missing supplier_material, OLD001 missing supplier_colour
            assert result['issues_found'] == 2
            assert result['tickets_created'] == 1


@pytest.mark.unit
@pytest.mark.scout
class TestCheckerSyncHealth:
    """Test sync health check."""

    def test_detects_stale_sync(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that stale sync is detected."""
        sys.path.insert(0, str(project_root / 'scout'))

        # Make sync look stale (48 hours old)
        mock_mavis_client.get_sync_status.return_value = {
            'status': 'idle',
            'last_successful_sync_at': '2025-01-13T10:00:00Z',  # Old date
            'last_error': None
        }

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client), \
             patch('services.checker.config') as mock_config:

            mock_config.check_sync_health = {
                'enabled': True,
                'stale_threshold_hours': 24,
                'priority': 'high',
                'ticket_type': 'incident'
            }

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_sync_health()

            assert result['issues_found'] > 0
            assert result['tickets_created'] == 1

    def test_detects_sync_failure(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test that sync failure is detected."""
        sys.path.insert(0, str(project_root / 'scout'))

        mock_mavis_client.get_sync_status.return_value = {
            'status': 'failed',
            'last_successful_sync_at': '2025-01-15T10:00:00Z',
            'last_error': 'Connection timeout to Unleashed API'
        }

        with patch('services.checker.db', scout_db), \
             patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client), \
             patch('services.checker.config') as mock_config:

            mock_config.check_sync_health = {
                'enabled': True,
                'stale_threshold_hours': 24,
                'priority': 'high',
                'ticket_type': 'incident'
            }

            from services.checker import CheckerService
            checker = CheckerService()

            result = checker._check_sync_health()

            assert result['issues_found'] > 0
            assert result['tickets_created'] == 1


@pytest.mark.unit
@pytest.mark.scout
class TestCheckerBotStatus:
    """Test bot status checking."""

    def test_get_bot_status(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test getting status of dependent bots."""
        sys.path.insert(0, str(project_root / 'scout'))

        with patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            status = checker.get_bot_status()

            assert status['mavis']['connected'] is True
            assert status['fiona']['connected'] is True
            assert status['sadie']['connected'] is True

    def test_get_bot_status_disconnected(
        self, scout_db, mock_mavis_client, mock_fiona_client, mock_sadie_client
    ):
        """Test getting status when bots are disconnected."""
        sys.path.insert(0, str(project_root / 'scout'))

        mock_mavis_client.check_connection.return_value = {
            'connected': False,
            'error': 'Connection refused'
        }

        with patch('services.checker.mavis_client', mock_mavis_client), \
             patch('services.checker.fiona_client', mock_fiona_client), \
             patch('services.checker.sadie_client', mock_sadie_client):

            from services.checker import CheckerService
            checker = CheckerService()

            status = checker.get_bot_status()

            assert status['mavis']['connected'] is False
            assert status['fiona']['connected'] is True
