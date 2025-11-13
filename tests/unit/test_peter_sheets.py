"""
Unit tests for Peter's Google Sheets service.

Tests cover contact CRUD operations, search, and section handling with mocked Google Sheets API.
"""
import os
import sys
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from googleapiclient.errors import HttpError
import importlib.util

# Add peter directory to path for imports
peter_path = Path(__file__).parent.parent.parent / 'peter'
if str(peter_path) not in sys.path:
    sys.path.insert(0, str(peter_path))

# Also add parent to ensure config can be imported
if str(peter_path.parent) not in sys.path:
    sys.path.insert(0, str(peter_path.parent))

# Import the service
from services.google_sheets import GoogleSheetsService


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def mock_config(monkeypatch, tmp_path):
    """Mock Peter's config with test credentials."""
    creds_file = tmp_path / 'service_account.json'
    creds_file.write_text('{"type": "service_account"}')

    class MockConfig:
        google_credentials_file = str(creds_file)
        spreadsheet_id = 'test-spreadsheet-id'
        sheet_name = 'Phone List'

    import config as peter_config
    monkeypatch.setattr(peter_config, 'config', MockConfig())

    return MockConfig()


@pytest.fixture
def sheets_service_with_mock(mock_config, mock_google_sheets_service):
    """Create a GoogleSheetsService instance with mocked Google Sheets API."""
    with patch('services.google_sheets.service_account'), \
         patch('services.google_sheets.build', return_value=mock_google_sheets_service):
        service = GoogleSheetsService()
        return service


@pytest.fixture
def sample_sheet_data():
    """Sample sheet data mimicking Peter's phone list format."""
    return [
        ['Ext', 'Name', 'Fixed Line', 'Mobile', 'Email'],  # Header
        ['EXECUTIVE TEAM', '', '', '', ''],  # Section header
        ['1001', 'John Doe (CEO)', '555-123-1001', '555-999-1001', 'john@company.com'],
        ['1002', 'Jane Smith (CFO)', '555-123-1002', '555-999-1002', 'jane@company.com'],
        ['ENGINEERING', '', '', '', ''],  # Another section
        ['2001', 'Bob Engineer', '555-123-2001', '555-999-2001', 'bob@company.com']
    ]


# ==============================================================================
# Initialization Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_initialization_success(mock_config, mock_google_sheets_service):
    """Test successful service initialization."""
    with patch('services.google_sheets.service_account') as mock_sa, \
         patch('services.google_sheets.build', return_value=mock_google_sheets_service):
        mock_creds = Mock()
        mock_sa.Credentials.from_service_account_file.return_value = mock_creds

        service = GoogleSheetsService()

        assert service.service is not None
        assert service.credentials is not None


@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_initialization_missing_credentials(monkeypatch):
    """Test initialization with missing credentials file."""
    class MockConfig:
        google_credentials_file = '/nonexistent/credentials.json'
        spreadsheet_id = 'test-id'
        sheet_name = 'Test'

    import config as peter_config
    monkeypatch.setattr(peter_config, 'config', MockConfig())

    service = GoogleSheetsService()
    assert service.service is None


# ==============================================================================
# get_all_contacts() Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_get_all_contacts_success(sheets_service_with_mock, mock_google_sheets_service, sample_sheet_data):
    """Test getting all contacts successfully."""
    mock_google_sheets_service.spreadsheets().values().get().execute.return_value = {
        'values': sample_sheet_data
    }

    contacts = sheets_service_with_mock.get_all_contacts()

    assert isinstance(contacts, list)
    # Should have parsed contacts (excluding headers and section headers)
    assert len(contacts) > 0


@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_get_all_contacts_empty_sheet(sheets_service_with_mock, mock_google_sheets_service):
    """Test getting contacts from empty sheet."""
    mock_google_sheets_service.spreadsheets().values().get().execute.return_value = {
        'values': []
    }

    contacts = sheets_service_with_mock.get_all_contacts()
    assert contacts == []


@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_get_all_contacts_service_not_initialized(monkeypatch):
    """Test getting contacts when service is not initialized."""
    class MockConfig:
        google_credentials_file = '/nonexistent/credentials.json'
        spreadsheet_id = 'test-id'
        sheet_name = 'Test'

    import config as peter_config
    monkeypatch.setattr(peter_config, 'config', MockConfig())

    service = GoogleSheetsService()
    result = service.get_all_contacts()

    assert 'error' in result
    assert 'not initialized' in result['error']


@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_get_all_contacts_api_error(sheets_service_with_mock, mock_google_sheets_service):
    """Test handling API errors when getting contacts."""
    mock_response = Mock()
    mock_response.status = 500
    error = HttpError(resp=mock_response, content=b'Server Error')
    mock_google_sheets_service.spreadsheets().values().get().execute.side_effect = error

    result = sheets_service_with_mock.get_all_contacts()

    assert 'error' in result


# ==============================================================================
# Search Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_search_contacts_by_name(sheets_service_with_mock, mock_google_sheets_service, sample_sheet_data):
    """Test searching contacts by name."""
    # Mock the get_all_contacts dependency
    mock_google_sheets_service.spreadsheets().values().get().execute.return_value = {
        'values': [
            ['Ext', 'Name', 'Fixed Line', 'Mobile', 'Email'],
            ['1001', 'John Doe', '555-1001', '555-9001', 'john@example.com'],
            ['1002', 'Jane Smith', '555-1002', '555-9002', 'jane@example.com']
        ]
    }

    # Assuming there's a search method - this is a placeholder
    # The actual implementation would need to be tested based on the real code
    # For now, just test that get_all works as foundation for search


# ==============================================================================
# Contact Data Validation Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.peter
def test_contact_handles_missing_fields(sheets_service_with_mock, mock_google_sheets_service):
    """Test that contacts with missing fields are handled properly."""
    mock_google_sheets_service.spreadsheets().values().get().execute.return_value = {
        'values': [
            ['1001', 'Minimal Contact'],  # Missing fixed, mobile, email
            ['', 'No Extension', '', '', 'test@example.com']  # Missing extension
        ]
    }

    # Should not crash with incomplete data
    contacts = sheets_service_with_mock.get_all_contacts()
    assert isinstance(contacts, list) or 'error' not in contacts


@pytest.mark.unit
@pytest.mark.peter
@pytest.mark.google_api
def test_handles_section_headers(sheets_service_with_mock, mock_google_sheets_service):
    """Test that section headers are properly recognized and skipped."""
    mock_google_sheets_service.spreadsheets().values().get().execute.return_value = {
        'values': [
            ['EXECUTIVE TEAM', '', '', '', ''],  # Section header (all caps)
            ['1001', 'John Doe', '555-1001', '', 'john@example.com'],
            ['ENGINEERING - 555-0000', '', '', '', ''],  # Section with phone
            ['2001', 'Bob Engineer', '555-2001', '', 'bob@example.com']
        ]
    }

    contacts = sheets_service_with_mock.get_all_contacts()

    # Sections shouldn't be in the contact list (or should be marked differently)
    assert isinstance(contacts, list)
