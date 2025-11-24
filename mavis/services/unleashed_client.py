"""
Unleashed API Client

Handles communication with the Unleashed API including:
- Authentication (HMAC-SHA256 signature)
- Pagination
- Error handling and retries
"""

import hashlib
import hmac
import base64
import requests
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class UnleashedClient:
    """Client for the Unleashed API"""

    def __init__(
        self,
        api_id: str,
        api_key: str,
        base_url: str = "https://api.unleashedsoftware.com",
        page_size: int = 200,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        Initialize the Unleashed client.

        Args:
            api_id: Unleashed API ID
            api_key: Unleashed API Key
            base_url: Base URL for the API
            page_size: Number of records per page
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries for failed requests
        """
        self.api_id = api_id
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.page_size = page_size
        self.timeout = timeout
        self.max_retries = max_retries

    def _generate_signature(self, query_string: str) -> str:
        """
        Generate HMAC-SHA256 signature for Unleashed API authentication.

        The signature is computed over the query string (without the leading '?').
        """
        key_bytes = self.api_key.encode('utf-8')
        query_bytes = query_string.encode('utf-8')
        signature = hmac.new(key_bytes, query_bytes, hashlib.sha256).digest()
        return base64.b64encode(signature).decode('utf-8')

    def _get_headers(self, query_string: str) -> Dict[str, str]:
        """Get headers for an API request"""
        signature = self._generate_signature(query_string)
        return {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'api-auth-id': self.api_id,
            'api-auth-signature': signature
        }

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any] = None,
        method: str = 'GET'
    ) -> Dict[str, Any]:
        """
        Make a request to the Unleashed API.

        Args:
            endpoint: API endpoint (e.g., 'Products')
            params: Query parameters
            method: HTTP method

        Returns:
            JSON response as dict

        Raises:
            requests.RequestException: On request failure after retries
        """
        params = params or {}
        query_string = urlencode(params) if params else ''

        url = f"{self.base_url}/{endpoint}"
        if query_string:
            url = f"{url}?{query_string}"

        headers = self._get_headers(query_string)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"API request attempt {attempt + 1}: {method} {endpoint}")
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    # Simple backoff: wait longer between retries
                    import time
                    time.sleep(2 ** attempt)

        logger.error(f"All {self.max_retries} attempts failed for {endpoint}")
        raise last_error

    def _paginate(
        self,
        endpoint: str,
        items_key: str,
        extra_params: Dict[str, Any] = None,
        progress_callback: callable = None,
        max_records: int = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all pages of a paginated endpoint.

        Args:
            endpoint: API endpoint
            items_key: Key in response that contains the items list
            extra_params: Additional query parameters
            progress_callback: Optional callback(fetched_count) called after each page
            max_records: Optional limit on total records to fetch (for testing)

        Returns:
            Combined list of all items from all pages
        """
        all_items = []
        page = 1

        while True:
            # Unleashed API uses 'pageNumber' not 'page'
            params = {'pageSize': self.page_size, 'pageNumber': page}
            if extra_params:
                params.update(extra_params)

            logger.debug(f"Fetching {endpoint} page {page}")
            response = self._make_request(endpoint, params)

            items = response.get(items_key, [])
            if not items:
                break

            all_items.extend(items)
            logger.info(f"Fetched {len(items)} items from {endpoint} page {page} "
                       f"(total: {len(all_items)})")

            # Call progress callback if provided
            if progress_callback:
                progress_callback(len(all_items))

            # Check if we've hit the max_records limit
            if max_records and len(all_items) >= max_records:
                logger.info(f"Reached max_records limit ({max_records}), stopping pagination")
                break

            # Check if we've reached the last page
            pagination = response.get('Pagination', {})
            total_pages = pagination.get('NumberOfPages', 1)
            if page >= total_pages:
                break

            page += 1

        return all_items

    # ─────────────────────────────────────────────────────────────
    # Product Methods
    # ─────────────────────────────────────────────────────────────

    def fetch_all_products(self, progress_callback: callable = None, max_records: int = None) -> List[Dict[str, Any]]:
        """
        Fetch all products from Unleashed.

        Args:
            progress_callback: Optional callback(fetched_count) called after each page
            max_records: Optional limit on total records to fetch (for testing)

        Returns:
            List of product dictionaries
        """
        logger.info(f"Starting fetch of products from Unleashed (max: {max_records or 'unlimited'})")
        products = self._paginate('Products', 'Items', progress_callback=progress_callback, max_records=max_records)
        logger.info(f"Completed fetching {len(products)} products from Unleashed")
        return products

    def fetch_product(self, product_code: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a single product by code.

        Args:
            product_code: The product code to fetch

        Returns:
            Product dictionary or None if not found
        """
        try:
            response = self._make_request(
                'Products',
                params={'productCode': product_code}
            )
            items = response.get('Items', [])
            return items[0] if items else None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch product {product_code}: {e}")
            return None

    # ─────────────────────────────────────────────────────────────
    # Future Expansion Methods (stubbed)
    # ─────────────────────────────────────────────────────────────

    def fetch_all_customers(self) -> List[Dict[str, Any]]:
        """Fetch all customers from Unleashed (not yet implemented)"""
        raise NotImplementedError("Customer sync not yet implemented")

    def fetch_all_sales_orders(self) -> List[Dict[str, Any]]:
        """Fetch all sales orders from Unleashed (not yet implemented)"""
        raise NotImplementedError("Sales order sync not yet implemented")

    # ─────────────────────────────────────────────────────────────
    # Health Check
    # ─────────────────────────────────────────────────────────────

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the Unleashed API.

        Returns:
            Dict with 'success' bool and 'message' or 'error'
        """
        try:
            # Try to fetch the first page of products with a small page size
            response = self._make_request('Products', params={'pageSize': 1, 'page': 1})
            return {
                'success': True,
                'message': 'Successfully connected to Unleashed API'
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'error': str(e)
            }
