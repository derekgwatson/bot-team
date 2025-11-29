"""
Data collection service for gathering historical lead data.

This service queries Buz OData to collect and store daily lead counts
for trend analysis and marketing intelligence.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class DataCollectionService:
    """
    Service for collecting and storing daily lead data.

    Queries Buz OData feeds to get lead counts for specific dates,
    then stores them in the database for analytics.
    """

    def __init__(self, config, odata_factory, db):
        """
        Initialize the service.

        Args:
            config: Liam's config object
            odata_factory: ODataClientFactory for creating OData clients
            db: LeadsDatabase for storing lead counts
        """
        self.config = config
        self.odata_factory = odata_factory
        self.db = db

    def collect_daily_data(
        self,
        org_key: str,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Collect lead count for a single org/date and store it.

        Args:
            org_key: Organization key
            date: Date to collect (defaults to yesterday)

        Returns:
            Dict with collection result
        """
        if date is None:
            date = datetime.now(timezone.utc) - timedelta(days=1)

        date_str = date.strftime("%Y-%m-%d")

        try:
            org_config = self.config.get_org_config(org_key)

            # Query OData for lead count
            client = self.odata_factory.get_client(org_key)
            lead_count = client.get_leads_count(date_str)

            # Store in database
            self.db.store_daily_lead_count(
                org_key=org_key,
                date=date_str,
                lead_count=lead_count
            )

            logger.info(f"Collected data for {org_key} on {date_str}: {lead_count} leads")

            return {
                'success': True,
                'org_key': org_key,
                'date': date_str,
                'lead_count': lead_count
            }

        except ValueError as e:
            logger.warning(f"Org {org_key} not configured: {e}")
            return {
                'success': False,
                'org_key': org_key,
                'date': date_str,
                'error': str(e)
            }

        except Exception as e:
            logger.error(f"Error collecting data for {org_key} on {date_str}: {e}")
            return {
                'success': False,
                'org_key': org_key,
                'date': date_str,
                'error': str(e)
            }

    def collect_all_orgs(
        self,
        date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Collect lead data for all configured orgs on a specific date.

        Args:
            date: Date to collect (defaults to yesterday)

        Returns:
            Dict with overall results
        """
        if date is None:
            date = datetime.now(timezone.utc) - timedelta(days=1)

        date_str = date.strftime("%Y-%m-%d")

        results = {
            'date': date_str,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'orgs': {},
            'summary': {
                'total': 0,
                'success': 0,
                'failed': 0
            }
        }

        for org_key in self.config.available_orgs:
            result = self.collect_daily_data(org_key=org_key, date=date)
            results['orgs'][org_key] = result
            results['summary']['total'] += 1

            if result['success']:
                results['summary']['success'] += 1
            else:
                results['summary']['failed'] += 1

        logger.info(
            f"Data collection complete for {date_str}: "
            f"{results['summary']['success']} succeeded, "
            f"{results['summary']['failed']} failed"
        )

        return results

    def backfill_historical_data(
        self,
        org_key: str,
        days: int = 30,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Backfill historical data for an organization.

        Useful for populating the database with past data when first
        setting up analytics.

        Args:
            org_key: Organization key
            days: Number of days back to collect
            skip_existing: Skip dates that already have data

        Returns:
            Dict with backfill results
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)

        logger.info(f"Starting backfill for {org_key}: {start_date} to {end_date}")

        results = {
            'org_key': org_key,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'collected': [],
            'skipped': [],
            'errors': []
        }

        current = start_date
        while current <= end_date:
            date_str = current.strftime('%Y-%m-%d')

            # Skip if data already exists
            if skip_existing:
                existing = self.db.get_lead_count_for_date(org_key, date_str)
                if existing is not None:
                    results['skipped'].append(date_str)
                    current += timedelta(days=1)
                    continue

            # Collect data
            result = self.collect_daily_data(
                org_key=org_key,
                date=datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            )

            if result['success']:
                results['collected'].append({
                    'date': date_str,
                    'lead_count': result['lead_count']
                })
            else:
                results['errors'].append({
                    'date': date_str,
                    'error': result.get('error', 'Unknown error')
                })

            current += timedelta(days=1)

        logger.info(
            f"Backfill complete for {org_key}: "
            f"{len(results['collected'])} collected, "
            f"{len(results['skipped'])} skipped, "
            f"{len(results['errors'])} errors"
        )

        return results

    def backfill_all_orgs(
        self,
        days: int = 30,
        skip_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Backfill historical data for all organizations.

        Args:
            days: Number of days back to collect
            skip_existing: Skip dates that already have data

        Returns:
            Dict with results by org
        """
        results = {
            'days': days,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'orgs': {}
        }

        for org_key in self.config.available_orgs:
            results['orgs'][org_key] = self.backfill_historical_data(
                org_key=org_key,
                days=days,
                skip_existing=skip_existing
            )

        return results
