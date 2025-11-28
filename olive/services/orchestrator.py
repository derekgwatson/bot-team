"""
Olive's Orchestration Service
Coordinates offboarding workflow across multiple bots
"""

from typing import Dict, List, Any, Optional
from config import config
from database.db import db
from shared.http_client import BotHttpClient
import logging

logger = logging.getLogger(__name__)


class OffboardingOrchestrator:
    """Orchestrates the offboarding workflow across multiple bots"""

    def __init__(self):
        # Bot URLs will be determined dynamically based on dev config
        pass

    def _get_bot_url(self, bot_name: str) -> str:
        """
        Get the URL for a bot, respecting dev mode configuration.

        In dev mode, checks Flask session for overrides:
        - If session says use 'prod' for this bot, use prod URL
        - Otherwise use localhost (dev default)

        Returns the URL for the bot API
        """
        from flask import session, has_request_context

        # Check if we're in a request context and have dev config
        if has_request_context():
            dev_config = session.get('dev_bot_config', {})
            if dev_config.get(bot_name) == 'prod':
                # Use production URL
                return f"https://{bot_name}.watsonblinds.com.au"

        # Default to config.yaml (localhost for dev)
        return config.bots.get(bot_name, {}).get('url', f'http://localhost:800{ord(bot_name[0]) % 10}')

    def _get_bot_client(self, bot_name: str, timeout: int = 30) -> BotHttpClient:
        """Get a BotHttpClient for the specified bot."""
        return BotHttpClient(self._get_bot_url(bot_name), timeout=timeout)

    def start_offboarding(self, request_id: int) -> Dict[str, Any]:
        """
        Start the offboarding workflow for a request
        Returns: Dict with success status and results
        """
        request = db.get_offboarding_request(request_id)
        if not request:
            return {'success': False, 'error': 'Request not found'}

        # Update status to in_progress
        db.update_offboarding_status(request_id, 'in_progress')

        # Define workflow steps
        steps = self._create_workflow_steps(request)
        db.create_workflow_steps(request_id, steps)

        # Execute workflow steps
        results = {
            'request_id': request_id,
            'success': True,
            'steps': []
        }

        for step in steps:
            step_result = self._execute_step(request_id, step, request)
            results['steps'].append(step_result)

            # If a critical step fails, stop the workflow
            if not step_result.get('success') and step.get('critical', True):
                results['success'] = False
                db.update_offboarding_status(request_id, 'failed')
                break

        # If all steps succeeded, mark as completed
        if results['success']:
            db.update_offboarding_status(request_id, 'completed')
            db.log_activity(request_id, 'offboarding_completed',
                          'All offboarding steps completed successfully')

        return results

    def _create_workflow_steps(self, request: Dict) -> List[Dict]:
        """Create the workflow steps for offboarding"""
        steps = []
        order = 1

        # Step 1: Send notification about offboarding
        steps.append({
            'name': 'notify_offboarding',
            'order': order,
            'description': 'Notify HR/IT about staff offboarding',
            'critical': False
        })
        order += 1

        # Step 2: Check Peter for staff access information
        steps.append({
            'name': 'check_peter',
            'order': order,
            'description': 'Check staff record and access in Peter',
            'critical': True
        })
        order += 1

        # Step 3: Disable Google account
        steps.append({
            'name': 'disable_google',
            'order': order,
            'description': 'Suspend Google Workspace account',
            'critical': False  # Non-critical so we continue even if they don't have Google
        })
        order += 1

        # Step 4: Downgrade Zendesk account to end-user
        steps.append({
            'name': 'deactivate_zendesk',
            'order': order,
            'description': 'Downgrade Zendesk account to end-user',
            'critical': False
        })
        order += 1

        # Step 5: Remove Wiki access via Paige
        steps.append({
            'name': 'remove_wiki_access',
            'order': order,
            'description': 'Remove Wiki access via Paige',
            'critical': False
        })
        order += 1

        # Step 6: Remove Buz access (stubbed for now)
        steps.append({
            'name': 'remove_buz_access',
            'order': order,
            'description': 'Remove Buz access',
            'critical': False
        })
        order += 1

        # Step 7: Update Peter with finish date
        steps.append({
            'name': 'update_peter_finish_date',
            'order': order,
            'description': 'Update Peter with finish date and mark staff as finished',
            'critical': True
        })
        order += 1

        return steps

    def _execute_step(self, request_id: int, step: Dict, request_data: Dict) -> Dict[str, Any]:
        """Execute a single workflow step"""
        step_name = step['name']

        # Get the step ID from database
        steps_in_db = db.get_workflow_steps(request_id)
        step_id = None
        for s in steps_in_db:
            if s['step_name'] == step_name and s['step_order'] == step['order']:
                step_id = s['id']
                break

        if not step_id:
            logger.error(f"Could not find step {step_name} in database")
            return {'success': False, 'error': 'Step not found in database'}

        # Update step status to in_progress
        db.update_workflow_step(step_id, 'in_progress')
        db.log_activity(request_id, f'step_started_{step_name}',
                       f"Started step: {step.get('description', step_name)}")

        # Execute the step based on its name
        result = None
        try:
            if step_name == 'notify_offboarding':
                result = self._notify_offboarding(request_data)
            elif step_name == 'check_peter':
                result = self._check_peter(request_data)
            elif step_name == 'disable_google':
                result = self._disable_google(request_data)
            elif step_name == 'deactivate_zendesk':
                result = self._deactivate_zendesk(request_data)
            elif step_name == 'remove_wiki_access':
                result = self._remove_wiki_access(request_data)
            elif step_name == 'remove_buz_access':
                result = self._remove_buz_access(request_data)
            elif step_name == 'update_peter_finish_date':
                result = self._update_peter_finish_date(request_data)
            else:
                result = {'success': False, 'error': f'Unknown step: {step_name}'}

        except Exception as e:
            logger.exception(f"Error executing step {step_name}")
            result = {'success': False, 'error': str(e)}

        # Update step status based on result
        if result.get('success'):
            db.update_workflow_step(step_id, 'completed', success=True,
                                   result_data=result.get('data'))
            db.log_activity(request_id, f'step_completed_{step_name}',
                          f"Completed step: {step.get('description', step_name)}",
                          metadata=result.get('data'))

            # Update offboarding request with result data
            if step_name == 'check_peter' and result.get('data'):
                data = result['data']
                db.update_offboarding_results(
                    request_id,
                    peter_staff_id=data.get('staff_id'),
                    google_email=data.get('work_email'),
                    had_google_access=data.get('google_access', False),
                    had_zendesk_access=data.get('zendesk_access', False),
                    had_wiki_access=data.get('wiki_access', False),
                    wiki_username=data.get('wiki_username'),
                    zendesk_user_id=data.get('zendesk_user_id')
                )
        else:
            db.update_workflow_step(step_id, 'failed', success=False,
                                   error_message=result.get('error'))
            db.log_activity(request_id, f'step_failed_{step_name}',
                          f"Failed step: {step.get('description', step_name)} - {result.get('error')}")

        return result

    def _notify_offboarding(self, request_data: Dict) -> Dict[str, Any]:
        """Send email notification about offboarding"""
        from services.email_service import email_service

        success = email_service.send_offboarding_notification(request_data)

        if success:
            return {'success': True, 'data': {'notified': config.notification_email}}
        else:
            return {'success': False, 'error': 'Failed to send email notification'}

    def _check_peter(self, request_data: Dict) -> Dict[str, Any]:
        """Check Peter for staff information and system access"""
        try:
            # Search for staff member by name
            peter = self._get_bot_client('peter')
            response = peter.get('/api/staff', params={'name': request_data['full_name']})

            if response.status_code == 200:
                result = response.json()
                staff_list = result.get('staff', [])

                if not staff_list:
                    return {
                        'success': False,
                        'error': f"Staff member '{request_data['full_name']}' not found in Peter"
                    }

                # Take the first match
                staff = staff_list[0]

                # Derive wiki username from work email (firstname.lastname)
                work_email = staff.get('work_email', '')
                wiki_username = work_email.split('@')[0] if work_email else None

                return {
                    'success': True,
                    'data': {
                        'staff_id': staff.get('id'),
                        'work_email': work_email,
                        'google_access': staff.get('google_access', False),
                        'zendesk_access': staff.get('zendesk_access', False),
                        'wiki_access': staff.get('wiki_access', False),
                        'wiki_username': wiki_username,
                        'zendesk_user_id': staff.get('zendesk_user_id', '')
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Peter API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Peter: {str(e)}'}

    def _disable_google(self, request_data: Dict) -> Dict[str, Any]:
        """Suspend Google Workspace account via Fred"""
        # Check if user had Google access
        if not request_data.get('had_google_access'):
            return {'success': True, 'data': {'message': 'No Google access to remove'}}

        try:
            email = request_data.get('google_email')
            if not email:
                return {'success': False, 'error': 'No Google email found for user'}

            # Call Fred's API to suspend user
            fred = self._get_bot_client('fred')
            response = fred.patch(f'/api/users/{email}', json={'suspended': True})

            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'data': {
                        'email': email,
                        'suspended': True
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Fred API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Fred: {str(e)}'}

    def _deactivate_zendesk(self, request_data: Dict) -> Dict[str, Any]:
        """Downgrade Zendesk account to end-user via Zac"""
        # Check if user had Zendesk access
        if not request_data.get('had_zendesk_access'):
            return {'success': True, 'data': {'message': 'No Zendesk access to remove'}}

        try:
            user_id = request_data.get('zendesk_user_id')
            if not user_id:
                return {'success': False, 'error': 'No Zendesk user ID found'}

            # Call Zac's API to downgrade user to end-user (don't suspend, just remove agent access)
            zac = self._get_bot_client('zac')
            response = zac.patch(f'/api/users/{user_id}', json={'role': 'end-user'})

            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'data': {
                        'user_id': user_id,
                        'role': 'end-user'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Zac API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Zac: {str(e)}'}

    def _remove_wiki_access(self, request_data: Dict) -> Dict[str, Any]:
        """Remove Wiki access via Paige"""
        # Check if user had wiki access
        if not request_data.get('had_wiki_access'):
            return {'success': True, 'data': {'message': 'No wiki access to remove'}}

        try:
            wiki_username = request_data.get('wiki_username')
            if not wiki_username:
                return {'success': False, 'error': 'No wiki username found for user'}

            # Call Paige's API to delete the wiki user
            paige = self._get_bot_client('paige')
            response = paige.delete(f'/api/users/{wiki_username}')

            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'data': {
                        'wiki_username': wiki_username,
                        'removed': True
                    }
                }
            elif response.status_code == 404:
                # User not found in wiki - that's okay, maybe already removed
                return {
                    'success': True,
                    'data': {
                        'wiki_username': wiki_username,
                        'message': 'User not found in wiki (may have been previously removed)'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Paige API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Paige: {str(e)}'}

    def _remove_buz_access(self, request_data: Dict) -> Dict[str, Any]:
        """Remove Buz access - STUBBED for now"""
        # TODO: Implement Buz bot integration when available
        logger.info("Buz access removal - STUBBED (to be implemented)")

        return {
            'success': True,
            'data': {
                'message': 'Buz access removal - STUBBED (to be implemented)',
                'stubbed': True
            }
        }

    def _update_peter_finish_date(self, request_data: Dict) -> Dict[str, Any]:
        """Update Peter with finish date and mark staff as finished"""
        try:
            staff_id = request_data.get('peter_staff_id')
            if not staff_id:
                return {'success': False, 'error': 'No Peter staff ID found'}

            # Call Peter's API to update staff with finish date
            peter = self._get_bot_client('peter')
            response = peter.patch(f'/api/staff/{staff_id}', json={
                'status': 'finished',
                'finish_date': request_data['last_day']
            })

            if response.status_code in [200, 204]:
                return {
                    'success': True,
                    'data': {
                        'staff_id': staff_id,
                        'finish_date': request_data['last_day'],
                        'status': 'finished'
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Peter API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Peter: {str(e)}'}


# Global orchestrator instance
orchestrator = OffboardingOrchestrator()
