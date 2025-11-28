"""
OData client for Buz API.

Provides access to Buz OData feeds for leads and other reports.
"""
import logging
from typing import List, Dict, Any, Optional
from requests.auth import HTTPBasicAuth
import requests

logger = logging.getLogger(__name__)


class ODataClient:
    """
    Client for querying Buz OData feeds.

    Each organization has its own OData endpoint with separate credentials.
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        org_code: str,
        timeout: int = 30,
        http_client=None
    ):
        """
        Initialize the OData client.

        Args:
            base_url: The base URL for the OData service (e.g., https://api.buzmanager.com/reports/WATSO)
            username: Username for HTTP Basic Auth
            password: Password for HTTP Basic Auth
            org_code: The organization code (for logging/tracking)
            timeout: Request timeout in seconds
            http_client: Optional HTTP client for testing (defaults to requests)
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.org_code = org_code
        self.timeout = timeout
        self.auth = HTTPBasicAuth(username, password)
        self.http_client = http_client or requests

    def get(
        self,
        endpoint: str,
        filters: Optional[List[str]] = None,
        select: Optional[List[str]] = None,
        top: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Send a GET request to the OData service.

        Args:
            endpoint: The endpoint to query (e.g., 'LeadsReport')
            filters: List of OData filter conditions (joined with 'and')
            select: List of fields to select (optional)
            top: Maximum number of records to return (optional)

        Returns:
            List of records from the OData feed

        Raises:
            requests.RequestException: If the request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        params = {}

        # Build $filter parameter
        if filters:
            filter_query = " and ".join(filters)
            params["$filter"] = filter_query

        # Build $select parameter
        if select:
            params["$select"] = ",".join(select)

        # Build $top parameter
        if top:
            params["$top"] = str(top)

        logger.info(f"OData request to {self.org_code}: {endpoint} with filters: {filters}")

        try:
            response = self.http_client.get(
                url,
                params=params,
                auth=self.auth,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            records = data.get("value", [])

            logger.info(f"OData response from {self.org_code}: {len(records)} records")
            return records

        except requests.exceptions.Timeout:
            logger.error(f"OData request to {self.org_code} timed out after {self.timeout}s")
            raise

        except requests.exceptions.HTTPError as e:
            logger.error(f"OData request to {self.org_code} failed with HTTP error: {e}")
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"OData request to {self.org_code} failed: {e}")
            raise

    def get_leads(
        self,
        date_taken: str,
        filters: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get leads for a specific date.

        Args:
            date_taken: Date in ISO format (YYYY-MM-DD)
            filters: Additional filter conditions

        Returns:
            List of lead records
        """
        # OData date filter format
        date_filter = f"DateTaken ge {date_taken}T00:00:00Z and DateTaken lt {date_taken}T23:59:59Z"

        all_filters = [date_filter]
        if filters:
            all_filters.extend(filters)

        return self.get("LeadsReport", filters=all_filters)

    def get_leads_count(self, date_taken: str) -> int:
        """
        Get count of leads for a specific date.

        This is more efficient than fetching all leads if you only need the count.

        Args:
            date_taken: Date in ISO format (YYYY-MM-DD)

        Returns:
            Number of leads for that date
        """
        leads = self.get_leads(date_taken, filters=None)
        return len(leads)

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the OData connection by making a simple request.

        Returns:
            Dict with success status and any error message
        """
        try:
            # Try to get just 1 record to verify connection
            self.get("LeadsReport", top=1)
            return {"success": True, "org_code": self.org_code}
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                return {
                    "success": False,
                    "org_code": self.org_code,
                    "error": "Authentication failed - check credentials"
                }
            return {
                "success": False,
                "org_code": self.org_code,
                "error": f"HTTP error: {e.response.status_code}"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "org_code": self.org_code,
                "error": str(e)
            }


class ODataClientFactory:
    """
    Factory for creating OData clients from config.

    Caches clients by org_key for reuse.
    """

    def __init__(self, config):
        """
        Initialize the factory.

        Args:
            config: Liam's config object
        """
        self.config = config
        self._clients = {}

    def get_client(self, org_key: str) -> ODataClient:
        """
        Get an OData client for the specified organization.

        Args:
            org_key: Organization key (e.g., 'canberra', 'dd')

        Returns:
            Configured ODataClient

        Raises:
            ValueError: If org is not configured or missing credentials
        """
        if org_key in self._clients:
            return self._clients[org_key]

        org_config = self.config.get_org_config(org_key)

        client = ODataClient(
            base_url=org_config["url"],
            username=org_config["username"],
            password=org_config["password"],
            org_code=org_config["code"],
            timeout=self.config.request_timeout
        )

        self._clients[org_key] = client
        return client

    def get_all_clients(self) -> Dict[str, ODataClient]:
        """
        Get OData clients for all configured organizations.

        Returns:
            Dict of org_key -> ODataClient
        """
        clients = {}
        for org_key in self.config.available_orgs:
            try:
                clients[org_key] = self.get_client(org_key)
            except ValueError as e:
                logger.warning(f"Skipping org {org_key}: {e}")
        return clients
