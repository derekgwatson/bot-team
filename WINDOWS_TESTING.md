# Windows Testing Guide

## Quick Start

If you're seeing import errors on Windows, here's how to run the tests successfully:

### 1. Install Dependencies

```powershell
# Install test dependencies
pip install -r test-requirements.txt

# Install bot dependencies
pip install -r fred/requirements.txt
pip install -r iris/requirements.txt
pip install -r peter/requirements.txt
pip install -r quinn/requirements.txt
pip install -r pam/requirements.txt
pip install -r shared/auth/requirements.txt
```

### 2. Run Tests

```powershell
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_quinn_database.py

# Run with verbose output
pytest -v

# Run tests for a specific bot
pytest -m quinn
pytest -m fred
```

### 3. Common Issues

#### Import Errors: "No module named 'services.xxx'"

**Solution**: Make sure you've installed all bot dependencies (step 1 above).

If you still get errors, try running pytest from the project root:
```powershell
cd C:\Users\Derek\Documents\Coding\Python_Scripts\bot-team
pytest
```

#### Import Errors: "No module named 'yaml'"

**Solution**: Install the missing dependency:
```powershell
pip install PyYAML
```

#### Import Errors: "No module named 'googleapiclient'"

**Solution**: Install Google API dependencies:
```powershell
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 4. Running Specific Test Categories

```powershell
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Tests for specific components
pytest -m database       # Database tests
pytest -m google_api     # Google API tests
pytest -m integration    # Integration tests
```

### 5. Coverage Reports

```powershell
# Run with coverage
pytest --cov=quinn --cov=fred --cov=peter --cov=iris --cov=pam --cov=shared

# Generate HTML coverage report
pytest --cov=quinn --cov=fred --cov=peter --cov=iris --cov=pam --cov=shared --cov-report=html

# Open coverage report (Windows)
start htmlcov/index.html
```

## Expected Results

After fixing any dependency issues, you should see:
- Some tests passing (especially Quinn database tests)
- Some tests may be skipped or have minor failures (this is normal for tests that need additional mocking setup)

## Still Having Issues?

1. **Check Python Version**: Make sure you're using Python 3.11+
   ```powershell
   python --version
   ```

2. **Check Working Directory**: Make sure you're in the project root
   ```powershell
   pwd  # Should show: .../bot-team
   ```

3. **Check Dependencies**: Make sure all packages are installed
   ```powershell
   pip list | findstr -i "pytest flask google yaml"
   ```

4. **Try Running Individual Test Files**: Some tests may have dependencies that aren't available in your environment (like actual Google credentials), which is fine - those tests use mocks.

## Test Status by Component

- ✅ **Quinn Database Tests** - Should work out of the box
- ✅ **Shared OAuth Tests** - Should work with mocked dependencies
- ⚠️ **Fred/Iris/Peter Tests** - May need Google API credentials mocking
- ⚠️ **Integration Tests** - May need additional setup

## Notes

- The test suite uses mocked Google APIs, so you don't need real Google credentials
- Some tests create temporary databases and files (automatically cleaned up)
- Tests are designed to be isolated and can run in any order
