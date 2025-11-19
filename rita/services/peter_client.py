# rita/services/peter_client.py
import os
from shared.http_client import BotHttpClient

PETER_BASE_URL = os.getenv("PETER_BASE_URL", "https://peter.watsonblinds.com.au")
_client = BotHttpClient(PETER_BASE_URL)


def lookup_staff_by_details(email: str, first_name: str, last_name: str) -> dict | None:
    resp = _client.post(
        "/api/staff/lookup",
        json={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        },
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if not data.get("found"):
        return None
    return data["staff"]
