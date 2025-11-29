"""
Leads verification service.

Handles daily verification that leads are being recorded in Buz OData feeds.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from shared.http_client import BotHttpClient
from shared.config.ports import get_port

logger = logging.getLogger(__name__)


class LeadsVerificationService:
    """
    Service for verifying leads are flowing correctly from Buz.

    Runs daily checks to ensure leads are being recorded. If zero leads
    are found on a weekday, creates a Zendesk ticket for IT Support.
    """

    def __init__(self, config, odata_factory, db):
        """
        Initialize the service.

        Args:
            config: Liam's config object
            odata_factory: ODataClientFactory for creating OData clients
            db: LeadsDatabase for storing verification results
        """
        self.config = config
        self.odata_factory = odata_factory
        self.db = db

    def _get_sadie_client(self) -> BotHttpClient:
        """Get HTTP client for Sadie (Zendesk tickets)."""
        port = get_port("sadie")
        return BotHttpClient(f"http://localhost:{port}", timeout=30)

    def _get_zendesk_group_id(self, group_name: str) -> Optional[int]:
        """
        Look up Zendesk group ID by name.

        Args:
            group_name: Name of the group (e.g., 'IT Support')

        Returns:
            Group ID or None if not found
        """
        try:
            sadie = self._get_sadie_client()
            response = sadie.get("/api/groups")
            if response.status_code == 200:
                groups = response.json().get("groups", [])
                for group in groups:
                    if group.get("name", "").lower() == group_name.lower():
                        return group.get("id")
            logger.warning(f"Could not find Zendesk group '{group_name}'")
            return None
        except Exception as e:
            logger.error(f"Error looking up Zendesk group: {e}")
            return None

    def _create_zendesk_ticket(
        self,
        org_name: str,
        date_str: str,
        is_primary: bool,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a Zendesk ticket for zero leads or OData error alert.

        Args:
            org_name: Display name of the organization
            date_str: Date string (YYYY-MM-DD)
            is_primary: Whether this is a primary store (more urgent)
            error_message: Optional error message if this is an OData error

        Returns:
            Dict with ticket creation result
        """
        subject = self.config.subject_template.format(
            org_name=org_name,
            date=date_str
        )

        # Adjust subject if it's an error
        if error_message:
            subject = f"Buz OData Error: {org_name} - {date_str}"

        # More detailed description
        if error_message:
            # OData error case
            description = (
                f"OData query failed for {org_name} on {date_str}.\n\n"
                f"Error: {error_message}\n\n"
                f"This likely indicates a problem with the Buz OData service or backup.\n\n"
                f"Please contact the Buz vendor to check the OData service status.\n\n"
                f"This ticket was automatically created by Liam (Buz Leads Monitor)."
            )
            priority = "high"  # Errors are always high priority
        elif is_primary:
            description = (
                f"Zero leads were recorded for {org_name} on {date_str}.\n\n"
                f"This is a PRIMARY store where we expect leads every business day. "
                f"This likely indicates a problem with the Buz OData backup.\n\n"
                f"Please contact the Buz vendor to check the backup status.\n\n"
                f"This ticket was automatically created by Liam (Buz Leads Monitor)."
            )
            priority = "high"
        else:
            description = (
                f"Zero leads were recorded for {org_name} on {date_str}.\n\n"
                f"While this may be legitimate for a regional store, please verify:\n"
                f"1. Was the store open that day?\n"
                f"2. Were there genuinely no inquiries?\n\n"
                f"If neither applies, there may be an issue with the Buz OData backup.\n\n"
                f"This ticket was automatically created by Liam (Buz Leads Monitor)."
            )
            priority = "normal"

        # Look up group ID
        group_id = self._get_zendesk_group_id(self.config.zendesk_group)

        try:
            sadie = self._get_sadie_client()
            response = sadie.post("/api/tickets", json={
                "subject": subject,
                "description": description,
                "priority": priority,
                "type": "incident",
                "group_id": group_id,
                "tags": ["liam", "odata-alert", "buz"]
            })

            if response.status_code == 201:
                ticket = response.json().get("ticket", {})
                logger.info(f"Created Zendesk ticket #{ticket.get('id')} for {org_name}")
                return {
                    "success": True,
                    "ticket_id": ticket.get("id"),
                    "ticket_url": ticket.get("url")
                }
            else:
                error = response.json().get("error", "Unknown error")
                logger.error(f"Failed to create ticket: {error}")
                return {"success": False, "error": error}

        except Exception as e:
            logger.error(f"Error creating Zendesk ticket: {e}")
            return {"success": False, "error": str(e)}

    def _is_skip_day(self, date: datetime) -> bool:
        """
        Check if the given date should be skipped (weekend).

        Args:
            date: Date to check

        Returns:
            True if this day should be skipped
        """
        return date.weekday() in self.config.skip_days

    def verify_org(
        self,
        org_key: str,
        date: Optional[datetime] = None,
        create_ticket: bool = True
    ) -> Dict[str, Any]:
        """
        Verify leads exist for a single organization on a given date.

        Args:
            org_key: Organization key (e.g., 'canberra')
            date: Date to check (defaults to yesterday)
            create_ticket: Whether to create a Zendesk ticket if zero leads

        Returns:
            Dict with verification result
        """
        if date is None:
            # Default to yesterday (in local time)
            date = datetime.now(timezone.utc) - timedelta(days=1)

        date_str = date.strftime("%Y-%m-%d")

        # Check if this is a skip day
        if self._is_skip_day(date):
            result = {
                "org_key": org_key,
                "date": date_str,
                "skipped": True,
                "reason": "Weekend",
                "lead_count": None
            }
            self.db.log_verification(
                org_key=org_key,
                date=date_str,
                lead_count=0,
                status="skipped",
                message="Weekend - verification skipped"
            )
            return result

        try:
            # Get org config
            org_config = self.config.get_org_config(org_key)
            org_name = org_config["display_name"]
            is_primary = org_config.get("is_primary", False)

            # Query OData for leads
            client = self.odata_factory.get_client(org_key)
            lead_count = client.get_leads_count(date_str)

            # Determine status
            if lead_count > 0:
                status = "ok"
                message = f"{lead_count} leads recorded"
                ticket_id = None
            else:
                status = "alert"
                message = "Zero leads recorded"
                ticket_id = None

                # Create ticket if enabled
                if create_ticket:
                    ticket_result = self._create_zendesk_ticket(
                        org_name=org_name,
                        date_str=date_str,
                        is_primary=is_primary
                    )
                    if ticket_result["success"]:
                        ticket_id = ticket_result.get("ticket_id")
                        message = f"Zero leads - ticket #{ticket_id} created"

            # Log to database
            self.db.log_verification(
                org_key=org_key,
                date=date_str,
                lead_count=lead_count,
                status=status,
                message=message,
                ticket_id=ticket_id
            )

            return {
                "org_key": org_key,
                "org_name": org_name,
                "date": date_str,
                "skipped": False,
                "lead_count": lead_count,
                "status": status,
                "message": message,
                "ticket_id": ticket_id,
                "is_primary": is_primary
            }

        except ValueError as e:
            # Org not configured
            logger.warning(f"Org {org_key} not configured: {e}")
            return {
                "org_key": org_key,
                "date": date_str,
                "skipped": True,
                "reason": str(e),
                "lead_count": None
            }

        except Exception as e:
            # OData request failed - treat like zero leads, create ticket
            logger.error(f"Error verifying {org_key}: {e}")

            # Try to get org config for ticket creation
            ticket_id = None
            try:
                org_config = self.config.get_org_config(org_key)
                org_name = org_config["display_name"]
                is_primary = org_config.get("is_primary", False)

                if create_ticket:
                    ticket_result = self._create_zendesk_ticket(
                        org_name=org_name,
                        date_str=date_str,
                        is_primary=is_primary,
                        error_message=str(e)
                    )
                    if ticket_result["success"]:
                        ticket_id = ticket_result.get("ticket_id")
            except ValueError:
                org_name = org_key
                is_primary = False

            message = f"OData error: {e}"
            if ticket_id:
                message = f"OData error - ticket #{ticket_id} created"

            self.db.log_verification(
                org_key=org_key,
                date=date_str,
                lead_count=0,
                status="error",
                message=message,
                ticket_id=ticket_id
            )

            return {
                "org_key": org_key,
                "date": date_str,
                "skipped": False,
                "lead_count": None,
                "status": "error",
                "message": message,
                "ticket_id": ticket_id
            }

    def verify_all(
        self,
        date: Optional[datetime] = None,
        create_tickets: bool = True
    ) -> Dict[str, Any]:
        """
        Verify leads for all configured organizations.

        Args:
            date: Date to check (defaults to yesterday)
            create_tickets: Whether to create Zendesk tickets for zero leads

        Returns:
            Dict with overall results and per-org details
        """
        if date is None:
            date = datetime.now(timezone.utc) - timedelta(days=1)

        date_str = date.strftime("%Y-%m-%d")

        results = {
            "date": date_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "orgs": {},
            "summary": {
                "total": 0,
                "ok": 0,
                "alert": 0,
                "error": 0,
                "skipped": 0
            }
        }

        for org_key in self.config.available_orgs:
            result = self.verify_org(
                org_key=org_key,
                date=date,
                create_ticket=create_tickets
            )

            results["orgs"][org_key] = result
            results["summary"]["total"] += 1

            if result.get("skipped"):
                results["summary"]["skipped"] += 1
            elif result.get("status") == "ok":
                results["summary"]["ok"] += 1
            elif result.get("status") == "alert":
                results["summary"]["alert"] += 1
            elif result.get("status") == "error":
                results["summary"]["error"] += 1

        logger.info(
            f"Verification complete for {date_str}: "
            f"{results['summary']['ok']} ok, "
            f"{results['summary']['alert']} alerts, "
            f"{results['summary']['error']} errors, "
            f"{results['summary']['skipped']} skipped"
        )

        return results

    def get_verification_history(
        self,
        org_key: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get verification history from database.

        Args:
            org_key: Optional filter by organization
            limit: Maximum number of records to return

        Returns:
            List of verification records
        """
        return self.db.get_verification_history(org_key=org_key, limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get verification statistics.

        Returns:
            Dict with stats by org and overall
        """
        return self.db.get_stats()

    def test_connections(self) -> Dict[str, Any]:
        """
        Test OData connections for all configured orgs.

        Returns:
            Dict with connection test results
        """
        results = {}
        for org_key in self.config.available_orgs:
            try:
                client = self.odata_factory.get_client(org_key)
                results[org_key] = client.test_connection()
            except ValueError as e:
                results[org_key] = {
                    "success": False,
                    "org_code": org_key,
                    "error": str(e)
                }
        return results
