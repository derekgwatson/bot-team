# Bot-Team Test Suite

Comprehensive test suite for the bot-team microservices project.

## Overview

This test suite provides unit and integration tests for all five bots:
- **Fred**: Google Workspace user management
- **Iris**: Google Workspace reporting and analytics
- **Peter**: Phone directory management via Google Sheets
- **Quinn**: External staff access management with database
- **Pam**: Directory web interface (Peter client)
- **Shared**: Google OAuth authentication

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and test configuration
├── unit/                                # Unit tests for individual components
│   ├── test_quinn_database.py          # Quinn database CRUD operations
│   ├── test_shared_oauth.py            # OAuth authentication flows
│   ├── test_fred_workspace.py          # Fred Google Workspace service
│   ├── test_peter_sheets.py            # Peter Google Sheets service
│   ├── test_iris_reports.py            # Iris Google Reports service
│   └── test_pam_client.py              # Pam's Peter API client
├── integration/                         # Integration tests across components
│   ├── test_quinn_workflow.py          # End-to-end approval workflows
│   └── test_bot_communication.py       # Bot-to-bot API communication
└── README.md                            # This file
```

## Prerequisites

### Install Test Dependencies

```bash
# From project root
pip install -r test-requirements.txt
```

Test dependencies include:
- **pytest**: Test framework
- **pytest-flask**: Flask app testing utilities
- **pytest-mock**: Mocking utilities
- **pytest-cov**: Code coverage reporting
- **responses**: HTTP request mocking
- **faker**: Test data generation
- **factory-boy**: Test fixture factories
- **freezegun**: Time mocking

## Running Tests

### Run All Tests

```bash
# From project root
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Tests for a specific bot
pytest -m quinn
pytest -m fred
pytest -m peter
pytest -m iris
pytest -m pam
pytest -m shared

# Run by test type marker
pytest -m unit
pytest -m integration
pytest -m database
pytest -m google_api
```

### Run with Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=html --cov-report=term-missing

# View HTML coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Run Specific Test Files

```bash
# Single test file
pytest tests/unit/test_quinn_database.py

# Specific test function
pytest tests/unit/test_quinn_database.py::test_add_staff_success

# Pattern matching
pytest -k "database"  # All tests with "database" in name
pytest -k "approval"  # All tests with "approval" in name
```

### Verbose Output

```bash
# Show test names and results
pytest -v

# Show print statements
pytest -s

# Show detailed failure info
pytest -vv

# Combine flags
pytest -vvs
```

## Test Markers

Tests are organized with pytest markers for easy filtering:

| Marker | Description |
|--------|-------------|
| `unit` | Unit tests for individual components |
| `integration` | Integration tests across components |
| `fred` | Tests for Fred bot (user management) |
| `iris` | Tests for Iris bot (reporting) |
| `peter` | Tests for Peter bot (phone directory) |
| `quinn` | Tests for Quinn bot (external access) |
| `pam` | Tests for Pam bot (directory web UI) |
| `shared` | Tests for shared components (auth) |
| `database` | Tests involving database operations |
| `google_api` | Tests with mocked Google API calls |
| `slow` | Tests that take longer to run |

### Using Markers

```bash
# Run only unit tests for Quinn
pytest -m "quinn and unit"

# Run integration tests excluding slow ones
pytest -m "integration and not slow"

# Run all database tests
pytest -m database
```

## Coverage Goals

The test suite aims for:
- **Overall Coverage**: 70%+ (enforced in `.coveragerc`)
- **Critical Components**: 80%+
  - Quinn database layer
  - Shared OAuth authentication
  - Fred user management
- **Google API Services**: 60%+ (harder due to external dependencies)

## Writing New Tests

### Unit Test Template

```python
import pytest
from unittest.mock import Mock, patch

@pytest.mark.unit
@pytest.mark.{bot_name}
def test_your_feature(fixture_name):
    """Test description."""
    # Arrange
    # ... setup test data

    # Act
    # ... call the function under test

    # Assert
    # ... verify expected behavior
    assert result == expected
```

### Integration Test Template

```python
import pytest

@pytest.mark.integration
@pytest.mark.{bot_name}
def test_your_workflow(fixture_name):
    """Test end-to-end workflow description."""
    # Step 1: Initial state
    # ...

    # Step 2: Perform action
    # ...

    # Step 3: Verify outcome
    assert outcome == expected
```

### Using Shared Fixtures

Common fixtures are available in `conftest.py`:

```python
def test_with_database(temp_db):
    """Use temporary database fixture."""
    # temp_db provides a clean SQLite database
    pass

def test_with_mock_google_api(mock_google_workspace_service):
    """Use mocked Google API fixture."""
    # All Google API calls are mocked
    pass

def test_with_sample_data(sample_user_data):
    """Use sample data fixtures."""
    # Pre-built test data available
    pass
```

## Continuous Integration

To run tests in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run tests
  run: |
    pip install -r test-requirements.txt
    pytest --cov=. --cov-report=xml

- name: Check coverage
  run: |
    coverage report --fail-under=70
```

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Tests can't find bot modules
# Solution: Run pytest from project root, not tests/ directory
cd /path/to/bot-team
pytest tests/
```

**Database Lock Errors**
```bash
# SQLite database locked
# Solution: Each test uses isolated temp database via fixtures
# If persists, check for unclosed connections
```

**Mock Not Working**
```bash
# Mocks not being applied
# Solution: Ensure patch target is correct import path
# Use patch('module.under.test.function') not patch('original.module.function')
```

### Debugging Tests

```bash
# Drop into debugger on failure
pytest --pdb

# Drop into debugger on first failure
pytest -x --pdb

# Show local variables on failure
pytest -l

# Run last failed tests only
pytest --lf
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Clear Names**: Use descriptive test function names
3. **One Assertion**: Focus on one behavior per test (when possible)
4. **Mock External**: Always mock external APIs (Google, HTTP requests)
5. **Clean Fixtures**: Use fixtures for setup/teardown
6. **Fast Tests**: Unit tests should run in milliseconds
7. **Meaningful Markers**: Tag tests appropriately for filtering

## Maintenance

### Adding Tests for New Features

1. Add unit tests in `tests/unit/test_{bot}_{feature}.py`
2. Add integration tests if feature spans multiple components
3. Update this README if new markers or patterns are introduced
4. Ensure coverage doesn't drop below 70%

### Updating Tests

When modifying bot code:
1. Run affected tests: `pytest -k {feature_name}`
2. Update tests to match new behavior
3. Add tests for new edge cases
4. Verify coverage: `pytest --cov={module}`

## Contributing

When submitting PRs:
- All tests must pass: `pytest`
- Coverage must be ≥70%: `pytest --cov=. --cov-report=term-missing`
- New features must include tests
- Follow existing test patterns and naming conventions

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-flask documentation](https://pytest-flask.readthedocs.io/)
- [responses documentation](https://github.com/getsentry/responses)
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
