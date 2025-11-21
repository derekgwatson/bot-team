"""
Monica Status Service
Business logic for determining device status from heartbeat data
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Literal
from monica.config import config

StatusType = Literal['online', 'degraded', 'offline']


class StatusService:
    """Service for computing device status based on heartbeat data"""

    def __init__(self):
        self.online_threshold = config.online_threshold
        self.degraded_threshold = config.degraded_threshold

    def compute_status(self, last_heartbeat_at: str) -> StatusType:
        """
        Compute device status based on last heartbeat timestamp

        Status logic:
        - online: last_heartbeat <= online_threshold minutes ago
        - degraded: online_threshold < last_heartbeat <= degraded_threshold minutes ago
        - offline: last_heartbeat > degraded_threshold minutes ago or never seen

        Args:
            last_heartbeat_at: ISO timestamp string or None

        Returns:
            Status: 'online', 'degraded', or 'offline'
        """
        if not last_heartbeat_at:
            return 'offline'

        try:
            last_seen = datetime.fromisoformat(last_heartbeat_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            minutes_ago = (now - last_seen).total_seconds() / 60

            if minutes_ago <= self.online_threshold:
                return 'online'
            elif minutes_ago <= self.degraded_threshold:
                return 'degraded'
            else:
                return 'offline'
        except (ValueError, AttributeError):
            return 'offline'

    def get_status_display(self, status: StatusType) -> Dict[str, str]:
        """
        Get display properties for a status

        Args:
            status: Status type

        Returns:
            Dictionary with color, emoji, and label
        """
        status_map = {
            'online': {
                'color': '#10b981',  # Green
                'emoji': '🟢',
                'label': 'Online'
            },
            'degraded': {
                'color': '#f59e0b',  # Amber
                'emoji': '🟡',
                'label': 'Degraded'
            },
            'offline': {
                'color': '#ef4444',  # Red
                'emoji': '🔴',
                'label': 'Offline'
            }
        }
        return status_map.get(status, status_map['offline'])

    def format_last_seen(self, last_heartbeat_at: str) -> str:
        """
        Format last heartbeat timestamp as human-readable text

        Args:
            last_heartbeat_at: ISO timestamp string or None

        Returns:
            Formatted string like "2 minutes ago" or "Never"
        """
        if not last_heartbeat_at:
            return "Never"

        try:
            last_seen = datetime.fromisoformat(last_heartbeat_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = now - last_seen

            if delta.total_seconds() < 60:
                return "Just now"
            elif delta.total_seconds() < 3600:
                minutes = int(delta.total_seconds() / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif delta.total_seconds() < 86400:
                hours = int(delta.total_seconds() / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                days = int(delta.total_seconds() / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
        except (ValueError, AttributeError):
            return "Unknown"

    def enrich_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich device data with computed status and display properties

        Args:
            device: Device dictionary from database

        Returns:
            Enriched device dictionary
        """
        status = self.compute_status(device.get('last_heartbeat_at'))
        display = self.get_status_display(status)
        last_seen = self.format_last_seen(device.get('last_heartbeat_at'))

        return {
            **device,
            'computed_status': status,
            'status_color': display['color'],
            'status_emoji': display['emoji'],
            'status_label': display['label'],
            'last_seen_text': last_seen
        }


# Global service instance
status_service = StatusService()
