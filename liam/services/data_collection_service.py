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

        Uses bulk OData query to fetch all leads in the date range at once,
        then aggregates by date. This is much faster than querying day-by-day
        (1 API call instead of N calls).

        Args:
            org_key: Organization key
            days: Number of days back to collect
            skip_existing: Skip dates that already have data

        Returns:
            Dict with backfill results
        """
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days - 1)

        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        logger.info(f"Starting bulk backfill for {org_key}: {start_str} to {end_str}")

        results = {
            'org_key': org_key,
            'start_date': start_str,
            'end_date': end_str,
            'collected': [],
            'skipped': [],
            'errors': []
        }

        try:
            # Get existing dates to skip (if skip_existing is True)
            existing_dates = set()
            if skip_existing:
                existing_dates = self.db.get_existing_dates_for_org(org_key, start_str, end_str)

            # Make ONE bulk API call to get all leads in range
            client = self.odata_factory.get_client(org_key)
            counts_by_date = client.get_leads_counts_by_date(start_str, end_str)

            # Process each day in the range
            current = start_date
            while current <= end_date:
                date_str = current.strftime('%Y-%m-%d')

                # Skip if data already exists
                if date_str in existing_dates:
                    results['skipped'].append(date_str)
                    current += timedelta(days=1)
                    continue

                # Get count from bulk results (0 if date not in results)
                lead_count = counts_by_date.get(date_str, 0)

                # Store in database
                self.db.store_daily_lead_count(
                    org_key=org_key,
                    date=date_str,
                    lead_count=lead_count
                )

                results['collected'].append({
                    'date': date_str,
                    'lead_count': lead_count
                })

                current += timedelta(days=1)

        except ValueError as e:
            logger.warning(f"Org {org_key} not configured: {e}")
            results['errors'].append({
                'date': 'all',
                'error': str(e)
            })

        except Exception as e:
            logger.error(f"Error in bulk backfill for {org_key}: {e}")
            results['errors'].append({
                'date': 'all',
                'error': str(e)
            })

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
