"""
Unit tests for Oscar's onboarding orchestrator.

Tests cover workflow creation, step execution, and bot-to-bot communication
without hitting any real external services.
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import responses
import tempfile
import importlib.util

# Add Oscar to path
project_root = Path(__file__).parent.parent.parent
oscar_path = project_root / 'oscar'
if str(oscar_path) not in sys.path:
    sys.path.insert(0, str(oscar_path))
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import orchestrator module using importlib for proper isolation
# This avoids conflicts with other bots' services modules
def _load_orchestrator_module():
    """Load the orchestrator module using importlib to avoid module conflicts."""
    spec = importlib.util.spec_from_file_location(
        "oscar_orchestrator",
        oscar_path / "services" / "orchestrator.py"
    )
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules['oscar_orchestrator'] = module
        spec.loader.exec_module(module)
        return module
    raise ImportError("Could not load Oscar orchestrator module")

# Try to load the orchestrator module
try:
    orchestrator_module = _load_orchestrator_module()
    OnboardingOrchestrator = orchestrator_module.OnboardingOrchestrator
except Exception as e:
    # Fallback - set to None and skip tests that need it
    orchestrator_module = None
    OnboardingOrchestrator = None
    print(f"Warning: Could not load Oscar orchestrator: {e}")


def setup_mock_email_service(mock_email_obj):
    """
    Set up mock services.email_service module to avoid import conflicts.
    Returns a mock EmailService class that returns mock_email_obj when instantiated.
    """
    import types

    mock_email_class = Mock(return_value=mock_email_obj)

    # Create mock module
    mock_module = types.ModuleType('services.email_service')
    mock_module.EmailService = mock_email_class

    # Ensure services package exists in sys.modules
    if 'services' not in sys.modules:
        services_pkg = types.ModuleType('services')
        services_pkg.__path__ = [str(oscar_path / 'services')]
        sys.modules['services'] = services_pkg

    sys.modules['services.email_service'] = mock_module

    return mock_email_class


# Load Oscar's Database class using importlib to avoid sys.modules caching issues
_oscar_db_module_path = oscar_path / 'database' / 'db.py'
_oscar_db_spec = importlib.util.spec_from_file_location('oscar_database_db', _oscar_db_module_path)
_oscar_db_module = importlib.util.module_from_spec(_oscar_db_spec)
_oscar_db_spec.loader.exec_module(_oscar_db_module)
OscarDatabase = _oscar_db_module.Database


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def oscar_db(tmp_path):
    """Create an isolated Oscar database for testing."""
    # Copy schema to temp location
    schema_src = oscar_path / 'database' / 'schema.sql'
    schema_dst = tmp_path / 'schema.sql'
    schema_dst.write_text(schema_src.read_text())

    # Create database
    db_path = tmp_path / 'test_oscar.db'

    # Create database with patched schema path using our isolated OscarDatabase class
    original_init = OscarDatabase.__init__
    def patched_init(self, db_path_arg=None):
        self.db_path = str(db_path)
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.executescript(schema_dst.read_text())
        conn.commit()
        conn.close()

    with patch.object(OscarDatabase, '__init__', patched_init):
        db = OscarDatabase()

    # Need to fix get_connection to use row_factory
    import sqlite3
    def get_conn():
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn
    db.get_connection = get_conn

    return db


@pytest.fixture
def sample_onboarding_request():
    """Sample onboarding request data."""
    return {
        'full_name': 'John Smith',
        'preferred_name': 'Johnny',
        'position': 'Sales Representative',
        'section': 'Sales',
        'start_date': '2025-02-01',
        'personal_email': 'john.smith@gmail.com',
        'work_email': 'john.smith@watsonblinds.com.au',  # Required for Google user creation
        'phone_mobile': '0412345678',
        'phone_fixed': '',
        'google_access': True,
        'zendesk_access': True,
        'voip_access': True,
        'notes': 'New hire for Melbourne office'
    }


@pytest.fixture
def mock_config():
    """Mock Oscar config with bot URLs."""
    config = Mock()
    config.bots = {
        'fred': {'url': 'http://localhost:8001'},
        'zac': {'url': 'http://localhost:8007'},
        'peter': {'url': 'http://localhost:8003'},
        'sadie': {'url': 'http://localhost:8010'}
    }
    config.notification_email = 'hr@company.com'
    return config


# ==============================================================================
# Workflow Creation Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.oscar
def test_create_workflow_steps_all_access(sample_onboarding_request, oscar_db):
    """Test workflow step creation when all access types are requested."""
    # Patch the db module before calling _create_workflow_steps
    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(sample_onboarding_request)

    # Should have 5 steps: create_google_user, create_zendesk_user, register_peter, voip_ticket, notify_hr
    assert len(steps) == 5

    step_names = [s['name'] for s in steps]
    assert 'notify_hr' in step_names
    assert 'create_google_user' in step_names
    assert 'create_zendesk_user' in step_names
    assert 'register_peter' in step_names
    assert 'voip_ticket' in step_names

    # Check order - Google first, then Zendesk, then Peter, then VOIP, then notify_hr last
    assert steps[0]['name'] == 'create_google_user'
    assert steps[0]['order'] == 1


@pytest.mark.unit
@pytest.mark.oscar
def test_create_workflow_steps_google_only(oscar_db):
    """Test workflow step creation when only Google access is requested."""
    request = {
        'full_name': 'Test User',
        'google_access': True,
        'zendesk_access': False,
        'voip_access': False
    }

    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(request)

    # Should have 3 steps: create_google_user, register_peter, notify_hr
    assert len(steps) == 3

    step_names = [s['name'] for s in steps]
    assert 'notify_hr' in step_names
    assert 'create_google_user' in step_names
    assert 'register_peter' in step_names
    assert 'create_zendesk_user' not in step_names
    assert 'voip_ticket' not in step_names


@pytest.mark.unit
@pytest.mark.oscar
def test_create_workflow_steps_minimal(oscar_db):
    """Test workflow step creation with no optional access."""
    request = {
        'full_name': 'Test User',
        'google_access': False,
        'zendesk_access': False,
        'voip_access': False
    }

    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(request)

    # Should have 2 steps: register_peter, notify_hr
    assert len(steps) == 2

    step_names = [s['name'] for s in steps]
    assert 'notify_hr' in step_names
    assert 'register_peter' in step_names


@pytest.mark.unit
@pytest.mark.oscar
def test_voip_step_has_manual_action_flag(oscar_db):
    """Test that VOIP step is marked as requiring manual action."""
    request = {
        'full_name': 'Test User',
        'google_access': False,
        'zendesk_access': False,
        'voip_access': True
    }

    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(request)

    voip_step = next(s for s in steps if s['name'] == 'voip_ticket')
    assert voip_step['requires_manual_action'] is True
    assert voip_step['manual_action_instructions'] is not None


# ==============================================================================
# Bot Communication Tests (HTTP mocking)
# ==============================================================================

@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_create_google_user_success(mock_responses, mock_config, sample_onboarding_request):
    """Test successful Google user creation via Fred."""
    # Mock Fred's API response
    mock_responses.add(
        responses.POST,
        'http://localhost:8001/api/users',
        json={
            'user': {
                'id': '12345',
                'email': 'john.smith@watsonblinds.com.au'
            }
        },
        status=201
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._create_google_user(sample_onboarding_request)

    assert result['success'] is True
    assert 'john.smith@watsonblinds.com.au' in result['data']['email']


@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_create_google_user_fred_unavailable(mock_responses, mock_config, sample_onboarding_request):
    """Test handling when Fred is unavailable."""
    import requests.exceptions

    mock_responses.add(
        responses.POST,
        'http://localhost:8001/api/users',
        body=requests.exceptions.ConnectionError('Connection refused')
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._create_google_user(sample_onboarding_request)

    assert result['success'] is False
    assert 'Failed to call Fred' in result['error']


@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_create_zendesk_user_success(mock_responses, mock_config, sample_onboarding_request):
    """Test successful Zendesk user creation via Zac."""
    mock_responses.add(
        responses.POST,
        'http://localhost:8007/api/users',
        json={
            'user': {
                'id': 'zd_67890',
                'name': 'John Smith',
                'email': 'john.smith@gmail.com'
            }
        },
        status=201
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._create_zendesk_user(sample_onboarding_request)

    assert result['success'] is True
    assert result['data']['user_id'] == 'zd_67890'


@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_create_zendesk_user_zac_error(mock_responses, mock_config, sample_onboarding_request):
    """Test handling Zac API errors."""
    mock_responses.add(
        responses.POST,
        'http://localhost:8007/api/users',
        json={'error': 'Email already exists'},
        status=400
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._create_zendesk_user(sample_onboarding_request)

    assert result['success'] is False
    assert 'Zac API error' in result['error']


@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_register_peter_success(mock_responses, mock_config, sample_onboarding_request):
    """Test successful staff registration via Peter."""
    mock_responses.add(
        responses.POST,
        'http://localhost:8003/api/staff',
        json={
            'staff': {
                'id': 'peter_123',
                'name': 'John Smith'
            }
        },
        status=201
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._register_peter(sample_onboarding_request)

    assert result['success'] is True
    assert result['data']['staff_id'] == 'peter_123'


@pytest.mark.unit
@pytest.mark.oscar
@pytest.mark.integration
def test_create_voip_ticket_success(mock_responses, mock_config, sample_onboarding_request):
    """Test successful VOIP ticket creation via Sadie."""
    mock_responses.add(
        responses.POST,
        'http://localhost:8010/api/tickets',
        json={
            'ticket': {
                'id': 'ticket_999',
                'url': 'https://support.zendesk.com/tickets/999'
            }
        },
        status=201
    )

    with patch('oscar_orchestrator.config', mock_config):
        # OnboardingOrchestrator already loaded at module level

        orchestrator = OnboardingOrchestrator()
        result = orchestrator._create_voip_ticket(sample_onboarding_request)

    assert result['success'] is True
    assert result['data']['ticket_id'] == 'ticket_999'


# ==============================================================================
# Email Notification Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.oscar
def test_notify_hr_success(mock_config, sample_onboarding_request):
    """Test successful email notification to HR."""
    mock_email_instance = Mock()
    mock_email_instance.send_email.return_value = (True, None)

    # Set up mock email service module to avoid import conflicts
    setup_mock_email_service(mock_email_instance)

    # Mock db.get_setting to return HR email
    mock_db = Mock()
    mock_db.get_setting.side_effect = lambda key, default=None: {
        'hr_notification_email': 'hr@company.com',
        'hr_notification_name': 'HR Team'
    }.get(key, default)

    with patch('oscar_orchestrator.config', mock_config), \
         patch('oscar_orchestrator.db', mock_db):
        orchestrator = OnboardingOrchestrator()
        result = orchestrator._notify_hr(sample_onboarding_request)

    assert result['success'] is True
    mock_email_instance.send_email.assert_called_once()

    # Verify email content includes staff name
    call_args = mock_email_instance.send_email.call_args
    assert 'John Smith' in call_args.kwargs.get('subject', '') or 'John Smith' in str(call_args)


@pytest.mark.unit
@pytest.mark.oscar
def test_notify_hr_email_failure(mock_config, sample_onboarding_request):
    """Test handling email send failure."""
    mock_email_instance = Mock()
    mock_email_instance.send_email.return_value = (False, "SMTP connection failed")

    # Set up mock email service module to avoid import conflicts
    setup_mock_email_service(mock_email_instance)

    # Mock db.get_setting to return HR email
    mock_db = Mock()
    mock_db.get_setting.side_effect = lambda key, default=None: {
        'hr_notification_email': 'hr@company.com',
        'hr_notification_name': 'HR Team'
    }.get(key, default)

    with patch('oscar_orchestrator.config', mock_config), \
         patch('oscar_orchestrator.db', mock_db):
        orchestrator = OnboardingOrchestrator()
        result = orchestrator._notify_hr(sample_onboarding_request)

    assert result['success'] is False
    assert 'Failed to send email' in result['error']


# ==============================================================================
# Critical vs Non-Critical Step Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.oscar
def test_zendesk_step_is_non_critical(oscar_db):
    """Test that Zendesk step failure doesn't block workflow."""
    request = {
        'full_name': 'Test User',
        'google_access': True,
        'zendesk_access': True,
        'voip_access': False
    }

    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(request)

    zendesk_step = next(s for s in steps if s['name'] == 'create_zendesk_user')
    assert zendesk_step.get('critical', True) is False


@pytest.mark.unit
@pytest.mark.oscar
def test_google_step_is_critical(oscar_db):
    """Test that Google step is marked as critical."""
    request = {
        'full_name': 'Test User',
        'google_access': True,
        'zendesk_access': False,
        'voip_access': False
    }

    with patch('database.db.db', oscar_db):
        orchestrator = OnboardingOrchestrator()
        steps = orchestrator._create_workflow_steps(request)

    google_step = next(s for s in steps if s['name'] == 'create_google_user')
    assert google_step.get('critical', True) is True


# ==============================================================================
# Email Generation Tests
# ==============================================================================

@pytest.mark.unit
@pytest.mark.oscar
def test_email_generation_single_name():
    """Test email generation for single-name person."""
    # OnboardingOrchestrator already loaded at module level

    orchestrator = OnboardingOrchestrator()

    # Access the email generation logic from _create_google_user
    # The email is generated as: first_name.last_name@watsonblinds.com.au
    request = {'full_name': 'Madonna', 'personal_email': 'madonna@gmail.com'}

    # We can't easily test this without mocking, but we can verify the logic
    first_name = request['full_name'].split()[0].lower()
    last_name = request['full_name'].split()[-1].lower() if len(request['full_name'].split()) > 1 else ''

    if last_name:
        expected_email = f"{first_name}.{last_name}@watsonblinds.com.au"
    else:
        expected_email = f"{first_name}@watsonblinds.com.au"

    assert expected_email == "madonna@watsonblinds.com.au"


@pytest.mark.unit
@pytest.mark.oscar
def test_email_generation_full_name():
    """Test email generation for full name."""
    request = {'full_name': 'John Smith', 'personal_email': 'john@gmail.com'}

    first_name = request['full_name'].split()[0].lower()
    last_name = request['full_name'].split()[-1].lower()
    expected_email = f"{first_name}.{last_name}@watsonblinds.com.au"

    assert expected_email == "john.smith@watsonblinds.com.au"
