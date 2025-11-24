"""
Checker service for Scout

Runs periodic checks to detect discrepancies between systems.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from config import config
from database.db import db
from services.bot_clients import mavis_client, fiona_client, sadie_client, peter_client, fred_client

logger = logging.getLogger(__name__)


class CheckerService:
    """Service that runs system checks and raises tickets for issues"""

    # Issue type constants
    ISSUE_MISSING_DESCRIPTION = 'missing_description'
    ISSUE_OBSOLETE_FABRIC = 'obsolete_fabric'
    ISSUE_INCOMPLETE_DESCRIPTION = 'incomplete_description'
    ISSUE_SYNC_STALE = 'sync_stale'
    ISSUE_SYNC_FAILED = 'sync_failed'
    ISSUE_USER_SYNC_MISMATCH = 'user_sync_mismatch'

    def run_all_checks(self) -> dict:
        """
        Run all enabled checks and return results.

        Returns:
            dict with check results and summary
        """
        run_id = db.start_check_run()
        logger.info(f"Starting check run {run_id}")

        results = {
            'checks': {},
            'issues_found': 0,
            'tickets_created': 0,
            'errors': []
        }

        try:
            # Check Mavis sync health
            if config.check_sync_health.get('enabled', True):
                try:
                    sync_result = self._check_sync_health()
                    results['checks']['sync_health'] = sync_result
                    results['issues_found'] += sync_result.get('issues_found', 0)
                    results['tickets_created'] += sync_result.get('tickets_created', 0)
                except Exception as e:
                    logger.exception("Error in sync health check")
                    results['errors'].append(f"sync_health: {str(e)}")

            # Check for missing descriptions
            if config.check_missing_descriptions.get('enabled', True):
                try:
                    missing_result = self._check_missing_descriptions()
                    results['checks']['missing_descriptions'] = missing_result
                    results['issues_found'] += missing_result.get('issues_found', 0)
                    results['tickets_created'] += missing_result.get('tickets_created', 0)
                except Exception as e:
                    logger.exception("Error in missing descriptions check")
                    results['errors'].append(f"missing_descriptions: {str(e)}")

            # Check for obsolete fabrics
            if config.check_obsolete_fabrics.get('enabled', True):
                try:
                    obsolete_result = self._check_obsolete_fabrics()
                    results['checks']['obsolete_fabrics'] = obsolete_result
                    results['issues_found'] += obsolete_result.get('issues_found', 0)
                    results['tickets_created'] += obsolete_result.get('tickets_created', 0)
                except Exception as e:
                    logger.exception("Error in obsolete fabrics check")
                    results['errors'].append(f"obsolete_fabrics: {str(e)}")

            # Check for incomplete descriptions
            if config.check_incomplete_descriptions.get('enabled', True):
                try:
                    incomplete_result = self._check_incomplete_descriptions()
                    results['checks']['incomplete_descriptions'] = incomplete_result
                    results['issues_found'] += incomplete_result.get('issues_found', 0)
                    results['tickets_created'] += incomplete_result.get('tickets_created', 0)
                except Exception as e:
                    logger.exception("Error in incomplete descriptions check")
                    results['errors'].append(f"incomplete_descriptions: {str(e)}")

            # Check for user sync mismatches (Peter vs Fred/Google)
            if config.check_user_sync.get('enabled', True):
                try:
                    user_sync_result = self._check_user_sync()
                    results['checks']['user_sync'] = user_sync_result
                    results['issues_found'] += user_sync_result.get('issues_found', 0)
                    results['tickets_created'] += user_sync_result.get('tickets_created', 0)
                except Exception as e:
                    logger.exception("Error in user sync check")
                    results['errors'].append(f"user_sync: {str(e)}")

            # Complete check run
            error_msg = '; '.join(results['errors']) if results['errors'] else None
            db.complete_check_run(
                run_id,
                issues_found=results['issues_found'],
                tickets_created=results['tickets_created'],
                check_results=results['checks'],
                error_message=error_msg
            )

            logger.info(
                f"Check run {run_id} completed: "
                f"{results['issues_found']} issues found, "
                f"{results['tickets_created']} tickets created"
            )

        except Exception as e:
            logger.exception(f"Fatal error in check run {run_id}")
            db.complete_check_run(run_id, error_message=str(e))
            raise

        return results

    def _check_sync_health(self) -> dict:
        """Check Mavis sync health"""
        logger.info("Running sync health check")
        result = {
            'issues_found': 0,
            'tickets_created': 0,
            'details': {}
        }

        try:
            sync_status = mavis_client.get_sync_status()
            result['details']['sync_status'] = sync_status

            status = sync_status.get('status')
            last_success = sync_status.get('last_successful_sync_at')
            last_error = sync_status.get('last_error')

            # Check for sync failure
            if status == 'failed' and last_error:
                issue_key = 'sync_failed'
                if not db.is_issue_reported(self.ISSUE_SYNC_FAILED, issue_key):
                    result['issues_found'] += 1
                    ticket = self._create_ticket_for_issue(
                        self.ISSUE_SYNC_FAILED,
                        issue_key,
                        subject="Mavis Unleashed Sync Failed",
                        description=(
                            f"The Mavis Unleashed product sync has failed.\n\n"
                            f"Error: {last_error}\n\n"
                            f"Please investigate and manually trigger a sync if needed."
                        ),
                        priority=config.check_sync_health.get('priority', 'high'),
                        ticket_type=config.check_sync_health.get('ticket_type', 'incident')
                    )
                    if ticket:
                        result['tickets_created'] += 1
                else:
                    # Update last seen
                    db.record_issue(
                        self.ISSUE_SYNC_FAILED,
                        issue_key,
                        {'error': last_error, 'status': status}
                    )
            else:
                # Resolve sync_failed if it was open
                db.resolve_issue(self.ISSUE_SYNC_FAILED, 'sync_failed')

            # Check for stale sync
            if last_success:
                threshold_hours = config.check_sync_health.get('stale_threshold_hours', 24)
                last_success_dt = datetime.fromisoformat(last_success.replace('Z', '+00:00'))
                hours_since = (datetime.now(timezone.utc) - last_success_dt).total_seconds() / 3600

                if hours_since > threshold_hours:
                    issue_key = 'sync_stale'
                    if not db.is_issue_reported(self.ISSUE_SYNC_STALE, issue_key):
                        result['issues_found'] += 1
                        ticket = self._create_ticket_for_issue(
                            self.ISSUE_SYNC_STALE,
                            issue_key,
                            subject="Mavis Unleashed Sync is Stale",
                            description=(
                                f"The Mavis Unleashed sync has not completed successfully "
                                f"in {hours_since:.1f} hours (threshold: {threshold_hours} hours).\n\n"
                                f"Last successful sync: {last_success}\n\n"
                                f"Please check the Mavis scheduler and Unleashed API connectivity."
                            ),
                            priority=config.check_sync_health.get('priority', 'high'),
                            ticket_type=config.check_sync_health.get('ticket_type', 'incident')
                        )
                        if ticket:
                            result['tickets_created'] += 1
                    else:
                        db.record_issue(
                            self.ISSUE_SYNC_STALE,
                            issue_key,
                            {'hours_since_sync': hours_since, 'last_success': last_success}
                        )
                else:
                    # Resolve stale issue if sync is now fresh
                    db.resolve_issue(self.ISSUE_SYNC_STALE, 'sync_stale')

        except Exception as e:
            logger.error(f"Error checking sync health: {e}")
            result['details']['error'] = str(e)

        return result

    def _check_missing_descriptions(self) -> dict:
        """Check for valid fabrics in Mavis without descriptions in Fiona"""
        logger.info("Running missing descriptions check")
        result = {
            'issues_found': 0,
            'tickets_created': 0,
            'details': {
                'mavis_count': 0,
                'fiona_count': 0,
                'missing_codes': []
            }
        }

        try:
            # Get valid fabrics from Mavis
            mavis_data = mavis_client.get_valid_fabrics(codes_only=True)
            mavis_codes = set(mavis_data.get('codes', []))
            result['details']['mavis_count'] = len(mavis_codes)

            # Get all fabric codes from Fiona
            fiona_codes = fiona_client.get_all_fabric_codes()
            result['details']['fiona_count'] = len(fiona_codes)

            # Find fabrics in Mavis but not in Fiona
            missing_codes = mavis_codes - fiona_codes
            result['details']['missing_codes'] = list(missing_codes)[:50]  # Limit for response size
            result['details']['missing_count'] = len(missing_codes)

            # Only create one ticket for all missing descriptions
            if missing_codes:
                issue_key = 'batch'  # Single issue for all missing descriptions
                existing = db.get_issue(self.ISSUE_MISSING_DESCRIPTION, issue_key)

                # Create ticket if we haven't reported this batch yet,
                # or if there are new codes since last report
                if not existing or existing['status'] != 'open':
                    result['issues_found'] = len(missing_codes)

                    codes_list = '\n'.join(sorted(missing_codes)[:30])
                    more_count = len(missing_codes) - 30 if len(missing_codes) > 30 else 0

                    ticket = self._create_ticket_for_issue(
                        self.ISSUE_MISSING_DESCRIPTION,
                        issue_key,
                        subject=f"[Scout] {len(missing_codes)} Fabrics Missing Descriptions",
                        description=(
                            f"Scout detected {len(missing_codes)} valid fabric(s) in Mavis "
                            f"that don't have descriptions in Fiona.\n\n"
                            f"Fabric codes:\n{codes_list}"
                            f"{f' ... and {more_count} more' if more_count else ''}\n\n"
                            f"Please add descriptions for these fabrics in Fiona."
                        ),
                        priority=config.check_missing_descriptions.get('priority', 'normal'),
                        ticket_type=config.check_missing_descriptions.get('ticket_type', 'task'),
                        details={'codes': list(missing_codes)}
                    )
                    if ticket:
                        result['tickets_created'] += 1
                else:
                    # Update the issue with current codes
                    db.record_issue(
                        self.ISSUE_MISSING_DESCRIPTION,
                        issue_key,
                        {'codes': list(missing_codes), 'count': len(missing_codes)}
                    )
                    result['issues_found'] = len(missing_codes)
            else:
                # Resolve if no missing codes
                db.resolve_issue(self.ISSUE_MISSING_DESCRIPTION, 'batch')

        except Exception as e:
            logger.error(f"Error checking missing descriptions: {e}")
            result['details']['error'] = str(e)

        return result

    def _check_obsolete_fabrics(self) -> dict:
        """Check for fabrics in Fiona that are no longer valid in Mavis"""
        logger.info("Running obsolete fabrics check")
        result = {
            'issues_found': 0,
            'tickets_created': 0,
            'details': {
                'mavis_count': 0,
                'fiona_count': 0,
                'obsolete_codes': []
            }
        }

        try:
            # Get valid fabrics from Mavis
            mavis_data = mavis_client.get_valid_fabrics(codes_only=True)
            mavis_codes = set(mavis_data.get('codes', []))
            result['details']['mavis_count'] = len(mavis_codes)

            # Get all fabric codes from Fiona
            fiona_codes = fiona_client.get_all_fabric_codes()
            result['details']['fiona_count'] = len(fiona_codes)

            # Find fabrics in Fiona but not in Mavis valid list
            obsolete_codes = fiona_codes - mavis_codes
            result['details']['obsolete_codes'] = list(obsolete_codes)[:50]
            result['details']['obsolete_count'] = len(obsolete_codes)

            # Create single ticket for obsolete fabrics
            if obsolete_codes:
                issue_key = 'batch'
                existing = db.get_issue(self.ISSUE_OBSOLETE_FABRIC, issue_key)

                if not existing or existing['status'] != 'open':
                    result['issues_found'] = len(obsolete_codes)

                    codes_list = '\n'.join(sorted(obsolete_codes)[:30])
                    more_count = len(obsolete_codes) - 30 if len(obsolete_codes) > 30 else 0

                    ticket = self._create_ticket_for_issue(
                        self.ISSUE_OBSOLETE_FABRIC,
                        issue_key,
                        subject=f"[Scout] {len(obsolete_codes)} Obsolete Fabric Descriptions",
                        description=(
                            f"Scout detected {len(obsolete_codes)} fabric description(s) in Fiona "
                            f"for products that are no longer valid in Mavis (obsolete, not sellable, "
                            f"or no longer categorized as fabric).\n\n"
                            f"Fabric codes:\n{codes_list}"
                            f"{f' ... and {more_count} more' if more_count else ''}\n\n"
                            f"These descriptions may be outdated and could be reviewed or removed."
                        ),
                        priority=config.check_obsolete_fabrics.get('priority', 'normal'),
                        ticket_type=config.check_obsolete_fabrics.get('ticket_type', 'task'),
                        details={'codes': list(obsolete_codes)}
                    )
                    if ticket:
                        result['tickets_created'] += 1
                else:
                    db.record_issue(
                        self.ISSUE_OBSOLETE_FABRIC,
                        issue_key,
                        {'codes': list(obsolete_codes), 'count': len(obsolete_codes)}
                    )
                    result['issues_found'] = len(obsolete_codes)
            else:
                db.resolve_issue(self.ISSUE_OBSOLETE_FABRIC, 'batch')

        except Exception as e:
            logger.error(f"Error checking obsolete fabrics: {e}")
            result['details']['error'] = str(e)

        return result

    def _check_incomplete_descriptions(self) -> dict:
        """Check for fabric descriptions missing required supplier fields"""
        logger.info("Running incomplete descriptions check")
        result = {
            'issues_found': 0,
            'tickets_created': 0,
            'details': {
                'total_checked': 0,
                'incomplete_codes': []
            }
        }

        try:
            # Get all fabrics from Fiona
            offset = 0
            limit = 1000
            incomplete_fabrics = []

            while True:
                fiona_data = fiona_client.get_all_fabrics(limit=limit, offset=offset)
                fabrics = fiona_data.get('fabrics', [])
                result['details']['total_checked'] += len(fabrics)

                for fabric in fabrics:
                    # Check for missing supplier fields
                    missing_fields = []
                    if not fabric.get('supplier_material'):
                        missing_fields.append('supplier_material')
                    if not fabric.get('supplier_colour'):
                        missing_fields.append('supplier_colour')

                    if missing_fields:
                        incomplete_fabrics.append({
                            'code': fabric['product_code'],
                            'missing': missing_fields
                        })

                if len(fabrics) < limit:
                    break
                offset += limit

            result['details']['incomplete_codes'] = [f['code'] for f in incomplete_fabrics[:50]]
            result['details']['incomplete_count'] = len(incomplete_fabrics)

            # Create single ticket for incomplete descriptions
            if incomplete_fabrics:
                issue_key = 'batch'
                existing = db.get_issue(self.ISSUE_INCOMPLETE_DESCRIPTION, issue_key)

                if not existing or existing['status'] != 'open':
                    result['issues_found'] = len(incomplete_fabrics)

                    # Format list with missing fields
                    lines = []
                    for f in incomplete_fabrics[:20]:
                        lines.append(f"  - {f['code']}: missing {', '.join(f['missing'])}")
                    codes_list = '\n'.join(lines)
                    more_count = len(incomplete_fabrics) - 20 if len(incomplete_fabrics) > 20 else 0

                    ticket = self._create_ticket_for_issue(
                        self.ISSUE_INCOMPLETE_DESCRIPTION,
                        issue_key,
                        subject=f"[Scout] {len(incomplete_fabrics)} Incomplete Fabric Descriptions",
                        description=(
                            f"Scout detected {len(incomplete_fabrics)} fabric description(s) in Fiona "
                            f"that are missing required supplier fields.\n\n"
                            f"Incomplete fabrics:\n{codes_list}"
                            f"{f' ... and {more_count} more' if more_count else ''}\n\n"
                            f"Please complete the supplier material and/or colour fields for these fabrics."
                        ),
                        priority=config.check_incomplete_descriptions.get('priority', 'low'),
                        ticket_type=config.check_incomplete_descriptions.get('ticket_type', 'task'),
                        details={'fabrics': incomplete_fabrics}
                    )
                    if ticket:
                        result['tickets_created'] += 1
                else:
                    db.record_issue(
                        self.ISSUE_INCOMPLETE_DESCRIPTION,
                        issue_key,
                        {'fabrics': incomplete_fabrics, 'count': len(incomplete_fabrics)}
                    )
                    result['issues_found'] = len(incomplete_fabrics)
            else:
                db.resolve_issue(self.ISSUE_INCOMPLETE_DESCRIPTION, 'batch')

        except Exception as e:
            logger.error(f"Error checking incomplete descriptions: {e}")
            result['details']['error'] = str(e)

        return result

    def _create_ticket_for_issue(
        self,
        issue_type: str,
        issue_key: str,
        subject: str,
        description: str,
        priority: str = 'normal',
        ticket_type: str = 'task',
        details: dict = None
    ) -> Optional[dict]:
        """Create a ticket via Sadie and record the issue"""

        # Skip ticket creation if disabled (e.g., in dev mode)
        if not config.create_tickets:
            logger.info(f"Ticket creation disabled - skipping ticket for {issue_type}:{issue_key}")
            # Still record the issue without a ticket
            db.record_issue(
                issue_type=issue_type,
                issue_key=issue_key,
                issue_details={**(details or {}), '_ticket_creation_disabled': True}
            )
            return None

        try:
            ticket = sadie_client.create_ticket(
                subject=subject,
                description=description,
                priority=priority,
                ticket_type=ticket_type,
                tags=['scout', 'automated', issue_type]
            )

            ticket_id = ticket.get('ticket_id')
            ticket_url = ticket.get('url')

            # Record the issue with ticket info
            db.record_issue(
                issue_type=issue_type,
                issue_key=issue_key,
                issue_details=details,
                ticket_id=ticket_id,
                ticket_url=ticket_url
            )

            logger.info(f"Created ticket {ticket_id} for {issue_type}:{issue_key}")
            return ticket

        except Exception as e:
            logger.error(f"Error creating ticket for {issue_type}:{issue_key}: {e}")
            # Still record the issue even if ticket creation fails
            db.record_issue(
                issue_type=issue_type,
                issue_key=issue_key,
                issue_details={'error': str(e), **(details or {})}
            )
            return None

    def _check_user_sync(self) -> dict:
        """Check for mismatches between Peter (staff directory) and Fred (Google Workspace)"""
        logger.info("Running user sync check")
        result = {
            'issues_found': 0,
            'tickets_created': 0,
            'details': {
                'peter_count': 0,
                'fred_count': 0,
                'in_fred_not_peter': [],
                'in_peter_not_fred': [],
                'in_peter_inactive_in_fred': []
            }
        }

        try:
            # Get active staff with Google access from Peter
            peter_data = peter_client.get_all_staff(status='active')
            peter_staff = [s for s in peter_data.get('staff', []) if s.get('google_access')]
            result['details']['peter_count'] = len(peter_staff)

            # Build set of emails Peter knows about (prefer google_primary_email, fall back to work_email)
            peter_emails = set()
            peter_by_email = {}
            for staff in peter_staff:
                email = staff.get('google_primary_email') or staff.get('work_email')
                if email:
                    peter_emails.add(email.lower())
                    peter_by_email[email.lower()] = staff

            # Get active users from Fred (Google Workspace)
            fred_users = fred_client.list_users(archived=False)
            result['details']['fred_count'] = len(fred_users)

            # Build set of emails Fred knows about
            fred_emails = set()
            fred_by_email = {}
            for user in fred_users:
                email = user.get('email')
                if email:
                    fred_emails.add(email.lower())
                    fred_by_email[email.lower()] = user

            # Find users in Fred but not in Peter
            in_fred_not_peter = fred_emails - peter_emails
            result['details']['in_fred_not_peter'] = list(in_fred_not_peter)

            # Find users in Peter but not in Fred (or suspended/archived in Fred)
            in_peter_not_fred = []
            in_peter_inactive = []
            for email in peter_emails:
                if email not in fred_emails:
                    in_peter_not_fred.append(email)

            result['details']['in_peter_not_fred'] = in_peter_not_fred

            # Check archived users in Fred that are still marked as having Google access in Peter
            archived_fred_users = fred_client.list_users(archived=True)
            for user in archived_fred_users:
                email = user.get('email', '').lower()
                if email in peter_emails:
                    in_peter_inactive.append({
                        'email': email,
                        'name': peter_by_email[email].get('name'),
                        'status_in_fred': 'archived' if user.get('archived') else 'suspended'
                    })

            result['details']['in_peter_inactive_in_fred'] = in_peter_inactive

            # Create tickets for issues found
            all_issues = []

            if in_fred_not_peter:
                all_issues.extend([{'type': 'in_fred_not_peter', 'email': e, 'user': fred_by_email[e]} for e in in_fred_not_peter])

            if in_peter_not_fred:
                all_issues.extend([{'type': 'in_peter_not_fred', 'email': e, 'user': peter_by_email[e]} for e in in_peter_not_fred])

            if in_peter_inactive:
                all_issues.extend([{'type': 'in_peter_inactive', **u} for u in in_peter_inactive])

            if all_issues:
                issue_key = 'batch'
                existing = db.get_issue(self.ISSUE_USER_SYNC_MISMATCH, issue_key)

                if not existing or existing['status'] != 'open':
                    result['issues_found'] = len(all_issues)

                    # Format the ticket description
                    lines = []
                    lines.append(f"Scout detected {len(all_issues)} user sync mismatch(es) between Peter (staff directory) and Fred (Google Workspace).\n")

                    if in_fred_not_peter:
                        lines.append(f"\n**Users in Google Workspace but not in Peter ({len(in_fred_not_peter)}):**")
                        for email in list(in_fred_not_peter)[:10]:
                            user = fred_by_email[email]
                            lines.append(f"  - {email} ({user.get('full_name', 'Unknown')})")
                        if len(in_fred_not_peter) > 10:
                            lines.append(f"  ... and {len(in_fred_not_peter) - 10} more")

                    if in_peter_not_fred:
                        lines.append(f"\n**Users in Peter with Google access but not in Google Workspace ({len(in_peter_not_fred)}):**")
                        for email in in_peter_not_fred[:10]:
                            user = peter_by_email[email]
                            lines.append(f"  - {email} ({user.get('name', 'Unknown')})")
                        if len(in_peter_not_fred) > 10:
                            lines.append(f"  ... and {len(in_peter_not_fred) - 10} more")

                    if in_peter_inactive:
                        lines.append(f"\n**Users in Peter with Google access but inactive in Google Workspace ({len(in_peter_inactive)}):**")
                        for item in in_peter_inactive[:10]:
                            lines.append(f"  - {item['email']} ({item['name']}) - {item['status_in_fred']}")
                        if len(in_peter_inactive) > 10:
                            lines.append(f"  ... and {len(in_peter_inactive) - 10} more")

                    lines.append("\nPlease review these discrepancies and update Peter or Fred as needed.")

                    ticket = self._create_ticket_for_issue(
                        self.ISSUE_USER_SYNC_MISMATCH,
                        issue_key,
                        subject=f"[Scout] {len(all_issues)} User Sync Mismatches (Peter vs Google Workspace)",
                        description='\n'.join(lines),
                        priority=config.check_user_sync.get('priority', 'normal'),
                        ticket_type=config.check_user_sync.get('ticket_type', 'task'),
                        details={
                            'in_fred_not_peter': list(in_fred_not_peter),
                            'in_peter_not_fred': in_peter_not_fred,
                            'in_peter_inactive_in_fred': in_peter_inactive
                        }
                    )
                    if ticket:
                        result['tickets_created'] += 1
                else:
                    # Update the issue with current mismatches
                    db.record_issue(
                        self.ISSUE_USER_SYNC_MISMATCH,
                        issue_key,
                        {
                            'issues': all_issues,
                            'count': len(all_issues)
                        }
                    )
                    result['issues_found'] = len(all_issues)
            else:
                # Resolve if no mismatches
                db.resolve_issue(self.ISSUE_USER_SYNC_MISMATCH, 'batch')

        except Exception as e:
            logger.error(f"Error checking user sync: {e}")
            result['details']['error'] = str(e)

        return result

    def get_bot_status(self) -> dict:
        """Get connection status for all dependent bots"""
        return {
            'mavis': mavis_client.check_connection(),
            'fiona': fiona_client.check_connection(),
            'sadie': sadie_client.check_connection(),
            'peter': peter_client.check_connection(),
            'fred': fred_client.check_connection()
        }


# Singleton instance
checker = CheckerService()
