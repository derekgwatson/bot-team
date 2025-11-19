import os
from urllib.parse import urljoin

import requests

BOT_API_KEY = os.getenv("BOT_API_KEY", "")


class BotHttpClient:
    """
    Simple HTTP client for talking to other bots.

    Always sends X-API-Key header.
    """

    def __init__(self, base_url: str, timeout: int = 10):
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.timeout = timeout

    def _headers(self) -> dict:
        headers = {}
        if BOT_API_KEY:
            headers["X-API-Key"] = BOT_API_KEY
        return headers

    def get(self, path: str, **kwargs):
        url = urljoin(self.base_url, path.lstrip("/"))
        return requests.get(
            url,
            headers=self._headers(),
            timeout=self.timeout,
            **kwargs,
        )

    def post(self, path: str, json=None, **kwargs):
        url = urljoin(self.base_url, path.lstrip("/"))
        return requests.post(
            url,
            headers=self._headers(),
            json=json,
            timeout=self.timeout,
            **kwargs,
        )
