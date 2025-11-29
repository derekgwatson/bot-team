"""
Analytics service for marketing intelligence.

Provides trend analysis, comparisons, and insights for lead data.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service for lead analytics and marketing intelligence.

    Provides insights like trends, comparisons, day-of-week patterns,
    and campaign impact analysis.
    """

    def __init__(self, config, db):
        """
        Initialize the service.

        Args:
            config: Liam's config object
            db: LeadsDatabase instance
        """
        self.config = config
        self.db = db

    def get_lead_trends(
        self,
        org_key: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get lead count trends over time.

        Args:
            org_key: Specific org (None = all orgs)
            days: Number of days to look back

        Returns:
            Dict with trend data including daily counts and statistics
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)

        # Get daily counts from database
        records = self.db.get_daily_lead_counts(
            org_key=org_key,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        # Organize by date and org
        if org_key:
            # Single org - simple list
            daily_data = {}
            for record in records:
                daily_data[record['date']] = record['lead_count']

            # Fill in missing dates with 0
            dates = []
            counts = []
            current = start_date
            while current <= end_date:
                date_str = current.strftime('%Y-%m-%d')
                dates.append(date_str)
                counts.append(daily_data.get(date_str, 0))
                current += timedelta(days=1)

            total = sum(counts)
            avg = total / len(counts) if counts else 0

            return {
                'org_key': org_key,
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'dates': dates,
                'counts': counts,
                'total': total,
                'average': round(avg, 1),
                'max': max(counts) if counts else 0,
                'min': min(counts) if counts else 0
            }
        else:
            # All orgs - organize by org
            by_org = defaultdict(lambda: defaultdict(int))
            for record in records:
                by_org[record['org_key']][record['date']] = record['lead_count']

            # Build series for each org
            org_series = {}
            dates = []
            current = start_date
            while current <= end_date:
                dates.append(current.strftime('%Y-%m-%d'))
                current += timedelta(days=1)

            for org in self.config.available_orgs:
                counts = [by_org[org].get(date, 0) for date in dates]
                total = sum(counts)
                avg = total / len(counts) if counts else 0

                org_series[org] = {
                    'counts': counts,
                    'total': total,
                    'average': round(avg, 1)
                }

            return {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'dates': dates,
                'orgs': org_series
            }

    def get_period_comparison(
        self,
        org_key: str,
        period: str = 'week'
    ) -> Dict[str, Any]:
        """
        Compare current period to previous period.

        Args:
            org_key: Organization key
            period: 'week' or 'month'

        Returns:
            Dict with current vs previous comparison
        """
        today = datetime.now(timezone.utc).date()

        if period == 'week':
            # Current week (Mon-Sun)
            days_since_monday = today.weekday()
            current_start = today - timedelta(days=days_since_monday)
            current_end = today
            previous_start = current_start - timedelta(days=7)
            previous_end = current_start - timedelta(days=1)
        else:  # month
            # Current month
            current_start = today.replace(day=1)
            current_end = today
            # Previous month
            previous_end = current_start - timedelta(days=1)
            previous_start = previous_end.replace(day=1)

        # Get counts for both periods
        current_records = self.db.get_daily_lead_counts(
            org_key=org_key,
            start_date=current_start.strftime('%Y-%m-%d'),
            end_date=current_end.strftime('%Y-%m-%d')
        )
        current_total = sum(r['lead_count'] for r in current_records)

        previous_records = self.db.get_daily_lead_counts(
            org_key=org_key,
            start_date=previous_start.strftime('%Y-%m-%d'),
            end_date=previous_end.strftime('%Y-%m-%d')
        )
        previous_total = sum(r['lead_count'] for r in previous_records)

        # Calculate change
        if previous_total > 0:
            change_pct = ((current_total - previous_total) / previous_total) * 100
        else:
            change_pct = 100.0 if current_total > 0 else 0.0

        return {
            'org_key': org_key,
            'period': period,
            'current': {
                'start_date': current_start.strftime('%Y-%m-%d'),
                'end_date': current_end.strftime('%Y-%m-%d'),
                'total': current_total,
                'average': round(current_total / len(current_records), 1) if current_records else 0
            },
            'previous': {
                'start_date': previous_start.strftime('%Y-%m-%d'),
                'end_date': previous_end.strftime('%Y-%m-%d'),
                'total': previous_total,
                'average': round(previous_total / len(previous_records), 1) if previous_records else 0
            },
            'change': {
                'absolute': current_total - previous_total,
                'percentage': round(change_pct, 1),
                'direction': 'up' if change_pct > 0 else 'down' if change_pct < 0 else 'flat'
            }
        }

    def get_day_of_week_analysis(
        self,
        org_key: Optional[str] = None,
        weeks: int = 4
    ) -> Dict[str, Any]:
        """
        Analyze lead patterns by day of week.

        Args:
            org_key: Specific org (None = all orgs)
            weeks: Number of weeks to analyze

        Returns:
            Dict with average leads per day of week
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=weeks * 7 - 1)

        records = self.db.get_daily_lead_counts(
            org_key=org_key,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )

        # Group by day of week (0=Monday, 6=Sunday)
        dow_totals = defaultdict(list)
        for record in records:
            date = datetime.strptime(record['date'], '%Y-%m-%d').date()
            dow = date.weekday()
            dow_totals[dow].append(record['lead_count'])

        # Calculate averages
        dow_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        dow_averages = {}
        for dow in range(7):
            counts = dow_totals.get(dow, [])
            avg = sum(counts) / len(counts) if counts else 0
            dow_averages[dow_names[dow]] = {
                'average': round(avg, 1),
                'sample_size': len(counts)
            }

        # Find best/worst days
        sorted_days = sorted(dow_averages.items(), key=lambda x: x[1]['average'], reverse=True)
        best_day = sorted_days[0][0] if sorted_days else None
        worst_day = sorted_days[-1][0] if sorted_days else None

        return {
            'org_key': org_key or 'all',
            'weeks_analyzed': weeks,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'by_day': dow_averages,
            'best_day': best_day,
            'worst_day': worst_day
        }

    def get_store_rankings(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Rank stores by lead performance.

        Args:
            days: Number of days to analyze

        Returns:
            List of stores ranked by total leads
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)

        rankings = []
        for org_key in self.config.available_orgs:
            org_config = self.config.get_org_config(org_key)

            records = self.db.get_daily_lead_counts(
                org_key=org_key,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            total = sum(r['lead_count'] for r in records)
            avg = total / days

            rankings.append({
                'org_key': org_key,
                'display_name': org_config['display_name'],
                'is_primary': org_config.get('is_primary', False),
                'total_leads': total,
                'average_per_day': round(avg, 1),
                'days': days
            })

        # Sort by total leads descending
        rankings.sort(key=lambda x: x['total_leads'], reverse=True)

        # Add rank positions
        for i, store in enumerate(rankings, 1):
            store['rank'] = i

        return rankings

    def get_campaign_impact(
        self,
        event_id: int,
        baseline_days: int = 7
    ) -> Dict[str, Any]:
        """
        Analyze the impact of a marketing campaign.

        Compares lead counts during campaign to baseline period before.

        Args:
            event_id: Marketing event ID
            baseline_days: Days before campaign to use as baseline

        Returns:
            Dict with campaign impact analysis
        """
        # Get event details
        events = self.db.get_marketing_events()
        event = next((e for e in events if e['id'] == event_id), None)

        if not event:
            return {'error': 'Event not found'}

        start_date = datetime.strptime(event['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(event['end_date'], '%Y-%m-%d').date() if event['end_date'] else start_date

        # Calculate baseline period
        baseline_end = start_date - timedelta(days=1)
        baseline_start = baseline_end - timedelta(days=baseline_days - 1)

        # Determine which orgs to analyze
        target_orgs = event['target_orgs'] if event['target_orgs'] else self.config.available_orgs

        impact_by_org = {}
        for org_key in target_orgs:
            # Get campaign period data
            campaign_records = self.db.get_daily_lead_counts(
                org_key=org_key,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )
            campaign_total = sum(r['lead_count'] for r in campaign_records)
            campaign_days = (end_date - start_date).days + 1
            campaign_avg = campaign_total / campaign_days if campaign_days > 0 else 0

            # Get baseline period data
            baseline_records = self.db.get_daily_lead_counts(
                org_key=org_key,
                start_date=baseline_start.strftime('%Y-%m-%d'),
                end_date=baseline_end.strftime('%Y-%m-%d')
            )
            baseline_total = sum(r['lead_count'] for r in baseline_records)
            baseline_avg = baseline_total / baseline_days if baseline_days > 0 else 0

            # Calculate lift
            if baseline_avg > 0:
                lift_pct = ((campaign_avg - baseline_avg) / baseline_avg) * 100
            else:
                lift_pct = 100.0 if campaign_avg > 0 else 0.0

            impact_by_org[org_key] = {
                'campaign_total': campaign_total,
                'campaign_avg': round(campaign_avg, 1),
                'baseline_avg': round(baseline_avg, 1),
                'lift_percentage': round(lift_pct, 1),
                'lift_direction': 'up' if lift_pct > 0 else 'down' if lift_pct < 0 else 'flat'
            }

        return {
            'event': {
                'id': event['id'],
                'name': event['name'],
                'type': event['event_type'],
                'start_date': event['start_date'],
                'end_date': event['end_date']
            },
            'baseline_period': {
                'start_date': baseline_start.strftime('%Y-%m-%d'),
                'end_date': baseline_end.strftime('%Y-%m-%d'),
                'days': baseline_days
            },
            'impact_by_org': impact_by_org
        }
