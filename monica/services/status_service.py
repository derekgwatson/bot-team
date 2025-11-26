"""
Monica Status Service
Business logic for determining device status from heartbeat data
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Literal, Optional
from monica.config import config

StatusType = Literal['online', 'degraded', 'offline', 'pending', 'sleeping']


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
            },
            'sleeping': {
                'color': '#6366f1',  # Indigo
                'emoji': '😴',
                'label': 'Sleeping'
            },
            'pending': {
                'color': '#6b7280',  # Gray
                'emoji': '⏳',
                'label': 'Awaiting Connection'
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

    def format_sleep_duration(self, seconds: Optional[int]) -> str:
        """
        Format sleep duration as human-readable text

        Args:
            seconds: Sleep duration in seconds

        Returns:
            Formatted string like "2h 30m" or "45m"
        """
        if not seconds:
            return ""

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def enrich_device(self, device: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich device data with computed status and display properties

        Args:
            device: Device dictionary from database

        Returns:
            Enriched device dictionary
        """
        # Check if this is a pending device (waiting for registration)
        agent_token = device.get('agent_token', '')
        is_pending = agent_token.startswith('PENDING_')
        registration_code = agent_token[8:] if is_pending else None

        if is_pending:
            status = 'pending'
            last_seen = 'Never connected'
        else:
            status = self.compute_status(device.get('last_heartbeat_at'))
            last_seen = self.format_last_seen(device.get('last_heartbeat_at'))

        display = self.get_status_display(status)

        # Process sleep/wake info
        last_wake_at = device.get('last_wake_at')
        last_sleep_duration = device.get('last_sleep_duration_seconds')
        wake_info = None
        recently_woke = False

        if last_wake_at:
            try:
                wake_time = datetime.fromisoformat(last_wake_at.replace('Z', '+00:00'))
                now = datetime.utcnow()
                minutes_since_wake = (now - wake_time).total_seconds() / 60

                # Consider "recently woke" if within the last 10 minutes
                if minutes_since_wake <= 10:
                    recently_woke = True

                sleep_duration_text = self.format_sleep_duration(last_sleep_duration)
                wake_info = {
                    'last_wake_at': last_wake_at,
                    'sleep_duration_seconds': last_sleep_duration,
                    'sleep_duration_text': sleep_duration_text,
                    'minutes_since_wake': int(minutes_since_wake),
                    'recently_woke': recently_woke
                }
            except (ValueError, AttributeError):
                pass

        # Determine if device is likely sleeping vs truly offline
        # A device is "sleeping" if it's offline but was recently active
        # and we have wake tracking enabled (last_wake_at exists)
        is_sleeping = False
        if status == 'offline' and not is_pending:
            # Check if the device has wake tracking and the last heartbeat gap
            # is consistent with sleep rather than network outage
            last_heartbeat_at = device.get('last_heartbeat_at')
            if last_heartbeat_at and last_wake_at:
                try:
                    last_hb = datetime.fromisoformat(last_heartbeat_at.replace('Z', '+00:00'))
                    last_wake = datetime.fromisoformat(last_wake_at.replace('Z', '+00:00'))
                    now = datetime.utcnow()

                    # If last wake was after last heartbeat, device woke up properly after sleeping
                    # If last heartbeat is recent enough (within 24h) and we have wake history,
                    # the current offline might be sleep
                    hours_since_heartbeat = (now - last_hb).total_seconds() / 3600
                    hours_since_wake = (now - last_wake).total_seconds() / 3600

                    # Heuristic: if device has woken before and offline for less than 12h,
                    # it's probably sleeping rather than having network issues
                    if hours_since_wake < 12 and hours_since_heartbeat < 12:
                        is_sleeping = True
                        status = 'sleeping'
                        display = self.get_status_display(status)
                except (ValueError, AttributeError):
                    pass

        return {
            **device,
            'computed_status': status,
            'status_color': display['color'],
            'status_emoji': display['emoji'],
            'status_label': display['label'],
            'last_seen_text': last_seen,
            'is_pending': is_pending,
            'registration_code': registration_code,
            'wake_info': wake_info,
            'recently_woke': recently_woke,
            'is_sleeping': is_sleeping
        }


# Global service instance
status_service = StatusService()
