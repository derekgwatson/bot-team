"""
Unit tests for Mavis Unleashed client.
"""

import os
import sys
import pytest
import responses
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ['TESTING'] = '1'
os.environ['SKIP_ENV_VALIDATION'] = '1'
os.environ['UNLEASHED_API_ID'] = 'test-api-id'
os.environ['UNLEASHED_API_KEY'] = 'test-api-key'

# Import after setting env vars
sys.path.insert(0, str(project_root / 'mavis'))
from services.unleashed_client import UnleashedClient


@pytest.fixture
def unleashed_client():
    """Create an Unleashed client for testing."""
    return UnleashedClient(
        api_id='test-api-id',
        api_key='test-api-key',
        base_url='https://api.unleashedsoftware.com',
        page_size=10,
        timeout=5,
        max_retries=1
    )


@pytest.mark.unit
@pytest.mark.mavis
class TestUnleashedClientAuthentication:
    """Test Unleashed client authentication."""

    def test_generate_signature(self, unleashed_client):
        """Test HMAC-SHA256 signature generation."""
        # Signature should be deterministic for same inputs
        sig1 = unleashed_client._generate_signature('page=1&pageSize=10')
        sig2 = unleashed_client._generate_signature('page=1&pageSize=10')
        assert sig1 == sig2

        # Different queries should produce different signatures
        sig3 = unleashed_client._generate_signature('page=2&pageSize=10')
        assert sig1 != sig3

    def test_get_headers(self, unleashed_client):
        """Test header generation."""
        headers = unleashed_client._get_headers('page=1')

        assert 'api-auth-id' in headers
        assert headers['api-auth-id'] == 'test-api-id'
        assert 'api-auth-signature' in headers
        assert 'Accept' in headers
        assert headers['Accept'] == 'application/json'


@pytest.mark.unit
@pytest.mark.mavis
class TestUnleashedClientProducts:
    """Test Unleashed client product operations."""

    @responses.activate
    def test_fetch_all_products_single_page(self, unleashed_client):
        """Test fetching products from a single page."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={
                'Items': [
                    {
                        'ProductCode': 'PROD001',
                        'ProductDescription': 'Test Product 1',
                        'DefaultSellPrice': 100.00
                    },
                    {
                        'ProductCode': 'PROD002',
                        'ProductDescription': 'Test Product 2',
                        'DefaultSellPrice': 200.00
                    }
                ],
                'Pagination': {
                    'NumberOfPages': 1,
                    'PageNumber': 1,
                    'PageSize': 10
                }
            },
            status=200
        )

        products = unleashed_client.fetch_all_products()

        assert len(products) == 2
        assert products[0]['ProductCode'] == 'PROD001'
        assert products[1]['ProductCode'] == 'PROD002'

    @responses.activate
    def test_fetch_all_products_multiple_pages(self, unleashed_client):
        """Test fetching products across multiple pages."""
        # Page 1
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={
                'Items': [
                    {'ProductCode': 'PROD001', 'ProductDescription': 'Product 1'}
                ],
                'Pagination': {
                    'NumberOfPages': 2,
                    'PageNumber': 1,
                    'PageSize': 10
                }
            },
            status=200
        )

        # Page 2
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={
                'Items': [
                    {'ProductCode': 'PROD002', 'ProductDescription': 'Product 2'}
                ],
                'Pagination': {
                    'NumberOfPages': 2,
                    'PageNumber': 2,
                    'PageSize': 10
                }
            },
            status=200
        )

        products = unleashed_client.fetch_all_products()

        assert len(products) == 2
        codes = [p['ProductCode'] for p in products]
        assert 'PROD001' in codes
        assert 'PROD002' in codes

    @responses.activate
    def test_fetch_product_found(self, unleashed_client):
        """Test fetching a single product."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={
                'Items': [
                    {
                        'ProductCode': 'SINGLE001',
                        'ProductDescription': 'Single Product',
                        'DefaultSellPrice': 50.00
                    }
                ]
            },
            status=200
        )

        product = unleashed_client.fetch_product('SINGLE001')

        assert product is not None
        assert product['ProductCode'] == 'SINGLE001'

    @responses.activate
    def test_fetch_product_not_found(self, unleashed_client):
        """Test fetching a non-existent product."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={'Items': []},
            status=200
        )

        product = unleashed_client.fetch_product('NONEXISTENT')
        assert product is None

    @responses.activate
    def test_fetch_product_api_error(self, unleashed_client):
        """Test handling API errors."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={'error': 'Unauthorized'},
            status=401
        )

        product = unleashed_client.fetch_product('ERROR')
        assert product is None


@pytest.mark.unit
@pytest.mark.mavis
class TestUnleashedClientConnectionTest:
    """Test Unleashed client connection testing."""

    @responses.activate
    def test_connection_success(self, unleashed_client):
        """Test successful connection test."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={'Items': []},
            status=200
        )

        result = unleashed_client.test_connection()

        assert result['success'] is True
        assert 'message' in result

    @responses.activate
    def test_connection_failure(self, unleashed_client):
        """Test failed connection test."""
        responses.add(
            responses.GET,
            'https://api.unleashedsoftware.com/Products',
            json={'error': 'Unauthorized'},
            status=401
        )

        result = unleashed_client.test_connection()

        assert result['success'] is False
        assert 'error' in result
