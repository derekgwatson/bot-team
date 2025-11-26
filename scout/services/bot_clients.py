"""
Bot client services for Scout

HTTP clients for communicating with Mavis, Fiona, and Sadie.
"""

import logging
from typing import Optional
from shared.http_client import BotHttpClient
from config import config

logger = logging.getLogger(__name__)


class MavisClient:
    """Client for communicating with Mavis (Unleashed Data Integration)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_mavis_url(), timeout=30)
        return self._client

    def get_valid_fabrics(self, codes_only: bool = True) -> dict:
        """
        Get list of valid fabric products from Mavis.

        Args:
            codes_only: If True, returns only product codes. If False, returns full product data.

        Returns:
            dict with 'codes' or 'products' list and 'count'
        """
        try:
            response = self.client.get(
                f"/api/products/fabrics?codes_only={str(codes_only).lower()}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting valid fabrics from Mavis: {e}")
            raise

    def get_sync_status(self) -> dict:
        """Get Mavis sync status"""
        try:
            response = self.client.get("/api/sync/status")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting sync status from Mavis: {e}")
            raise

    def get_health(self) -> dict:
        """Get Mavis health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Mavis: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Mavis is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status'),
                'url': config.get_mavis_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_mavis_url()
            }


class FionaClient:
    """Client for communicating with Fiona (Fabric Description Manager)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_fiona_url(), timeout=30)
        return self._client

    def get_all_fabrics(self, limit: int = 1000, offset: int = 0) -> dict:
        """
        Get all fabric descriptions from Fiona.

        Returns:
            dict with 'fabrics' list, 'count', 'total', 'limit', 'offset'
        """
        try:
            response = self.client.get(f"/api/fabrics/all?limit={limit}&offset={offset}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting fabrics from Fiona: {e}")
            raise

    def get_all_fabric_codes(self) -> set:
        """Get set of all fabric codes in Fiona"""
        all_codes = set()
        offset = 0
        limit = 1000

        while True:
            result = self.get_all_fabrics(limit=limit, offset=offset)
            fabrics = result.get('fabrics', [])

            for fabric in fabrics:
                all_codes.add(fabric['product_code'])

            if len(fabrics) < limit:
                break

            offset += limit

        return all_codes

    def get_fabric_stats(self) -> dict:
        """Get fabric statistics from Fiona"""
        try:
            response = self.client.get("/api/fabrics/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting fabric stats from Fiona: {e}")
            raise

    def bulk_lookup(self, codes: list) -> dict:
        """
        Bulk lookup fabrics by codes.

        Returns:
            dict with 'fabrics' list and 'not_found' list
        """
        try:
            response = self.client.post(
                "/api/fabrics/bulk",
                json={"operation": "lookup", "codes": codes}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error bulk looking up fabrics from Fiona: {e}")
            raise

    def get_health(self) -> dict:
        """Get Fiona health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Fiona: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Fiona is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status'),
                'url': config.get_fiona_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_fiona_url()
            }


class SadieClient:
    """Client for communicating with Sadie (Zendesk Ticket Manager)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_sadie_url(), timeout=30)
        return self._client

    def create_ticket(
        self,
        subject: str,
        description: str,
        priority: str = 'normal',
        ticket_type: str = 'task',
        tags: list = None
    ) -> dict:
        """
        Create a Zendesk ticket via Sadie.

        Args:
            subject: Ticket subject
            description: Ticket body/description
            priority: low, normal, high, urgent
            ticket_type: question, incident, problem, task
            tags: List of tags to add

        Returns:
            dict with ticket_id, url, etc.
        """
        try:
            payload = {
                'subject': subject,
                'description': description,
                'priority': priority,
                'type': ticket_type
            }
            if tags:
                payload['tags'] = tags

            response = self.client.post("/api/tickets", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error creating ticket via Sadie: {e}")
            raise

    def get_health(self) -> dict:
        """Get Sadie health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Sadie: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Sadie is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status'),
                'url': config.get_sadie_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_sadie_url()
            }


class PeterClient:
    """Client for communicating with Peter (Staff Directory)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_peter_url(), timeout=30)
        return self._client

    def get_all_staff(self, status: str = 'active') -> dict:
        """
        Get all staff members from Peter.

        Args:
            status: Filter by status (active, inactive, all)

        Returns:
            dict with 'staff' list and 'count'
        """
        try:
            response = self.client.get(f"/api/staff?status={status}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting staff from Peter: {e}")
            raise

    def get_health(self) -> dict:
        """Get Peter health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Peter: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Peter is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status', 'ok'),
                'url': config.get_peter_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_peter_url()
            }


class FredClient:
    """Client for communicating with Fred (Google Workspace Manager)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_fred_url(), timeout=30)
        return self._client

    def list_users(self, archived: bool = False) -> list:
        """
        Get list of Google Workspace users from Fred.

        Args:
            archived: If True, only return archived users

        Returns:
            List of user dicts with email, name, etc.
        """
        try:
            response = self.client.get(f"/api/users?archived={str(archived).lower()}")
            response.raise_for_status()
            data = response.json()
            return data.get('users', [])
        except Exception as e:
            logger.error(f"Error getting users from Fred: {e}")
            raise

    def get_health(self) -> dict:
        """Get Fred health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Fred: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Fred is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status', 'ok'),
                'url': config.get_fred_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_fred_url()
            }


class NigelClient:
    """Client for communicating with Nigel (Quote Price Monitor)"""

    def __init__(self):
        self._client = None

    @property
    def client(self) -> BotHttpClient:
        if self._client is None:
            self._client = BotHttpClient(config.get_nigel_url(), timeout=30)
        return self._client

    def get_discrepancies(self, resolved: bool = False) -> dict:
        """
        Get price discrepancies from Nigel.

        Args:
            resolved: If False, only return unresolved discrepancies

        Returns:
            dict with 'discrepancies' list and 'count'
        """
        try:
            response = self.client.get(f"/api/discrepancies?resolved={str(resolved).lower()}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting discrepancies from Nigel: {e}")
            raise

    def get_stats(self) -> dict:
        """Get monitoring statistics from Nigel"""
        try:
            response = self.client.get("/api/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting stats from Nigel: {e}")
            raise

    def get_health(self) -> dict:
        """Get Nigel health status"""
        try:
            response = self.client.get("/health", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting health from Nigel: {e}")
            raise

    def check_connection(self) -> dict:
        """Check if Nigel is reachable"""
        try:
            health = self.get_health()
            return {
                'connected': True,
                'status': health.get('status'),
                'url': config.get_nigel_url()
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e),
                'url': config.get_nigel_url()
            }


# Singleton instances
mavis_client = MavisClient()
fiona_client = FionaClient()
sadie_client = SadieClient()
peter_client = PeterClient()
fred_client = FredClient()
nigel_client = NigelClient()
