"""
Oscar's Orchestration Service
Coordinates onboarding workflow across multiple bots
"""

import json
import requests
from typing import Dict, List, Any, Optional
from config import config
from database.db import db
from shared.password_generator import generate_memorable_password
import logging

logger = logging.getLogger(__name__)


class OnboardingOrchestrator:
    """Orchestrates the onboarding workflow across multiple bots"""

    def __init__(self, dry_run: bool = False):
        """
        Initialize the orchestrator.

        Args:
            dry_run: If True, log what would happen without making actual API calls.
                    Useful for testing workflows before executing them for real.
        """
        self.dry_run = dry_run
        if dry_run:
            logger.info("DRY RUN MODE ENABLED - No actual changes will be made")

    def preview_onboarding(self, request_data: Dict) -> Dict[str, Any]:
        """
        Preview what an onboarding workflow would do without executing it.
        Useful for validation before running the actual workflow.

        Args:
            request_data: The onboarding request data

        Returns:
            Dict with preview of all steps that would be executed
        """
        steps = self._create_workflow_steps(request_data)

        # Use provided work email or generate a preview one
        work_email = request_data.get('work_email')
        if not work_email and request_data.get('google_access'):
            # Fallback: generate email from name (for preview only)
            first_name = request_data['full_name'].split()[0].lower()
            last_name = request_data['full_name'].split()[-1].lower() if len(
                request_data['full_name'].split()) > 1 else ''
            work_email = f"{first_name}.{last_name}@example.com" if last_name else f"{first_name}@example.com"

        preview = {
            'dry_run': True,
            'request_data': request_data,
            'work_email': work_email if request_data.get('google_access') else None,
            'workflow_steps': [],
            'bot_calls': []
        }

        for step in steps:
            step_preview = {
                'name': step['name'],
                'order': step['order'],
                'description': step.get('description', ''),
                'critical': step.get('critical', True),
                'requires_manual_action': step.get('requires_manual_action', False)
            }

            # Add details about what each step would do
            if step['name'] == 'notify_ian':
                step_preview['would_do'] = f"Send email to {config.notification_email}"
                preview['bot_calls'].append({
                    'bot': 'Mabel (email)',
                    'action': 'Send notification email',
                    'recipient': config.notification_email
                })

            elif step['name'] == 'create_google_user':
                # Parse name for Fred API
                name_parts = request_data['full_name'].split()
                first_name = name_parts[0]
                last_name = name_parts[-1] if len(name_parts) > 1 else ''

                step_preview['would_do'] = f"Create Google user: {work_email}"
                preview['bot_calls'].append({
                    'bot': 'Fred',
                    'url': self._get_bot_url('fred'),
                    'action': 'POST /api/users',
                    'payload': {
                        'email': work_email,
                        'first_name': first_name,
                        'last_name': last_name,
                        'recovery_email': request_data['personal_email']
                    }
                })

            elif step['name'] == 'create_zendesk_user':
                zd_email = work_email if request_data.get('google_access') else request_data['personal_email']
                step_preview['would_do'] = f"Create Zendesk agent: {request_data['full_name']} ({zd_email})"
                preview['bot_calls'].append({
                    'bot': 'Zac',
                    'url': self._get_bot_url('zac'),
                    'action': 'POST /api/users',
                    'payload': {
                        'name': request_data['full_name'],
                        'email': zd_email,
                        'role': 'agent'
                    }
                })

            elif step['name'] == 'register_peter':
                step_preview['would_do'] = f"Register in HR database: {request_data['full_name']}"
                preview['bot_calls'].append({
                    'bot': 'Peter',
                    'url': self._get_bot_url('peter'),
                    'action': 'POST /api/staff',
                    'payload': {
                        'name': request_data['full_name'],
                        'position': request_data['position'],
                        'section': request_data['section']
                    }
                })

            elif step['name'] == 'voip_ticket':
                step_preview['would_do'] = f"Create VOIP setup ticket for: {request_data['full_name']}"
                preview['bot_calls'].append({
                    'bot': 'Sadie',
                    'url': self._get_bot_url('sadie'),
                    'action': 'POST /api/tickets',
                    'payload': {
                        'subject': f"VOIP Setup Required: {request_data['full_name']}",
                        'type': 'task'
                    }
                })

            preview['workflow_steps'].append(step_preview)

        return preview

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

    def start_onboarding(self, request_id: int) -> Dict[str, Any]:
        """
        Start the onboarding workflow for a request
        Returns: Dict with success status and results
        """
        request = db.get_onboarding_request(request_id)
        if not request:
            return {'success': False, 'error': 'Request not found'}

        # Update status to in_progress
        db.update_onboarding_status(request_id, 'in_progress')

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
                db.update_onboarding_status(request_id, 'failed',
                                           f"Step '{step['name']}' failed: {step_result.get('error')}")
                break

        # If all steps succeeded, mark as completed
        if results['success']:
            db.update_onboarding_status(request_id, 'completed')
            db.log_activity(request_id, 'onboarding_completed',
                          'All onboarding steps completed successfully')

        return results

    def _create_workflow_steps(self, request: Dict) -> List[Dict]:
        """Create the workflow steps based on request requirements"""
        steps = []
        order = 1

        # Step 1: Notify Ian (HR/Payroll)
        steps.append({
            'name': 'notify_ian',
            'order': order,
            'description': 'Notify HR/Payroll (Ian) about new staff member',
            'critical': True
        })
        order += 1

        # Step 2: Create Google User (if required)
        if request.get('google_access'):
            steps.append({
                'name': 'create_google_user',
                'order': order,
                'description': 'Create Google Workspace user account',
                'critical': True
            })
            order += 1

        # Step 3: Create Zendesk User (if required)
        if request.get('zendesk_access'):
            steps.append({
                'name': 'create_zendesk_user',
                'order': order,
                'description': 'Create Zendesk account',
                'critical': False
            })
            order += 1

        # Step 4: Register with Peter (always done)
        steps.append({
            'name': 'register_peter',
            'order': order,
            'description': 'Register staff member in HR database',
            'critical': True
        })
        order += 1

        # Step 5: Create VOIP ticket (if required)
        if request.get('voip_access'):
            steps.append({
                'name': 'voip_ticket',
                'order': order,
                'description': 'Create Zendesk ticket for VOIP setup',
                'critical': False,
                'requires_manual_action': True,
                'manual_action_instructions': 'Create VOIP user account in PBX system'
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
            if step_name == 'notify_ian':
                result = self._notify_ian(request_data)
            elif step_name == 'create_google_user':
                result = self._create_google_user(request_data)
            elif step_name == 'create_zendesk_user':
                result = self._create_zendesk_user(request_data)
            elif step_name == 'register_peter':
                result = self._register_peter(request_data)
            elif step_name == 'voip_ticket':
                result = self._create_voip_ticket(request_data)
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

            # Update onboarding request with result data
            if step_name == 'create_google_user' and result.get('data', {}).get('email'):
                data = result['data']
                backup_codes_json = json.dumps(data.get('backup_codes', [])) if data.get('backup_codes') else None
                db.update_onboarding_results(
                    request_id,
                    google_user_email=data['email'],
                    google_user_password=data.get('password'),
                    google_backup_codes=backup_codes_json
                )
            elif step_name == 'create_zendesk_user' and result.get('data', {}).get('user_id'):
                db.update_onboarding_results(request_id,
                                            zendesk_user_id=result['data']['user_id'])
            elif step_name == 'register_peter' and result.get('data', {}).get('staff_id'):
                db.update_onboarding_results(request_id,
                                            peter_staff_id=result['data']['staff_id'])
            elif step_name == 'voip_ticket' and result.get('data', {}).get('ticket_id'):
                db.update_workflow_step(step_id, 'in_progress', success=True,
                                       zendesk_ticket_id=result['data']['ticket_id'])
        else:
            db.update_workflow_step(step_id, 'failed', success=False,
                                   error_message=result.get('error'))
            db.log_activity(request_id, f'step_failed_{step_name}',
                          f"Failed step: {step.get('description', step_name)} - {result.get('error')}")

        return result

    def _notify_ian(self, request_data: Dict) -> Dict[str, Any]:
        """Send email notification to Ian (HR/Payroll)"""
        from services.email_service import EmailService

        email_service = EmailService()
        subject = f"New Staff Onboarding: {request_data['full_name']}"

        # Build email body
        body = f"""
New staff member onboarding initiated:

Name: {request_data['full_name']}
Preferred Name: {request_data.get('preferred_name', 'N/A')}
Position: {request_data['position']}
Section: {request_data['section']}
Start Date: {request_data['start_date']}

Contact Information:
- Personal Email: {request_data['personal_email']}
- Mobile: {request_data.get('phone_mobile', 'N/A')}
- Fixed Line: {request_data.get('phone_fixed', 'N/A')}

System Access:
- Google Workspace: {'Yes' if request_data.get('google_access') else 'No'}
- Zendesk: {'Yes' if request_data.get('zendesk_access') else 'No'}
- VOIP: {'Yes' if request_data.get('voip_access') else 'No'}

Notes: {request_data.get('notes', 'None')}

---
This is an automated notification from Oscar (Staff Onboarding Bot)
"""

        success = email_service.send_email(
            to_email=config.notification_email,
            subject=subject,
            body=body
        )

        if success:
            return {'success': True, 'data': {'notified': config.notification_email}}
        else:
            return {'success': False, 'error': 'Failed to send email notification'}

    def _create_google_user(self, request_data: Dict) -> Dict[str, Any]:
        """Call Fred to create a Google Workspace user"""
        try:
            # Use provided work email
            email = request_data.get('work_email')
            if not email:
                return {'success': False, 'error': 'No work email provided'}

            # Parse name for Fred API
            name_parts = request_data['full_name'].split()
            first_name = name_parts[0]
            last_name = name_parts[-1] if len(name_parts) > 1 else ''

            # Generate a memorable password
            password = generate_memorable_password()

            # Call Fred's API to create user
            # Don't require password change so admin can log in first to set up 2FA
            response = requests.post(
                f"{self._get_bot_url('fred')}/api/users",
                json={
                    'email': email,
                    'first_name': first_name,
                    'last_name': last_name,
                    'password': password,
                    'change_password_at_next_login': False
                },
                headers={'X-API-Key': config.bot_api_key},
                timeout=30
            )

            if response.status_code not in [200, 201]:
                return {
                    'success': False,
                    'error': f"Fred API error: {response.status_code} - {response.text}"
                }

            # Generate backup codes via Fred's API
            backup_codes = []
            try:
                backup_response = requests.post(
                    f"{self._get_bot_url('fred')}/api/users/{email}/backup-codes",
                    headers={'X-API-Key': config.bot_api_key},
                    timeout=30
                )
                if backup_response.status_code == 200:
                    backup_result = backup_response.json()
                    backup_codes = backup_result.get('backup_codes', [])
            except Exception as e:
                logger.warning(f"Failed to generate backup codes: {e}")

            return {
                'success': True,
                'data': {
                    'email': email,
                    'password': password,
                    'backup_codes': backup_codes,
                    'fred_response': response.json()
                }
            }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Fred: {str(e)}'}

    def _create_zendesk_user(self, request_data: Dict) -> Dict[str, Any]:
        """Call Zac to create a Zendesk user"""
        try:
            # Use work email if Google access, otherwise use personal email
            email = request_data.get('work_email') or request_data.get('google_user_email') or request_data['personal_email']

            response = requests.post(
                f"{self._get_bot_url('zac')}/api/users",
                json={
                    'name': request_data['full_name'],
                    'email': email,
                    'role': 'agent'  # Default to agent role
                },
                headers={'X-API-Key': config.bot_api_key},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    'success': True,
                    'data': {
                        'user_id': result.get('user', {}).get('id'),
                        'zac_response': result
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Zac API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Zac: {str(e)}'}

    def _register_peter(self, request_data: Dict) -> Dict[str, Any]:
        """Call Peter to register the staff member"""
        try:
            # Use provided work email or fall back to results from Google user creation
            work_email = request_data.get('work_email') or request_data.get('google_user_email', '')

            response = requests.post(
                f"{self._get_bot_url('peter')}/api/staff",
                json={
                    'name': request_data['full_name'],
                    'position': request_data['position'],
                    'section': request_data['section'],
                    'phone_mobile': request_data.get('phone_mobile', ''),
                    'phone_fixed': request_data.get('phone_fixed', ''),
                    'work_email': work_email,
                    'personal_email': request_data['personal_email'],
                    'google_access': request_data.get('google_access', False),
                    'zendesk_access': request_data.get('zendesk_access', False),
                    'voip_access': request_data.get('voip_access', False),
                    'status': 'active',
                    'notes': request_data.get('notes', '')
                },
                headers={'X-API-Key': config.bot_api_key},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    'success': True,
                    'data': {
                        'staff_id': result.get('staff', {}).get('id'),
                        'peter_response': result
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Peter API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Peter: {str(e)}'}

    def _create_voip_ticket(self, request_data: Dict) -> Dict[str, Any]:
        """Call Sadie to create a Zendesk ticket for VOIP setup"""
        try:
            # Build ticket description with clear instructions
            description = f"""
New staff member requires VOIP setup:

Name: {request_data['full_name']}
Position: {request_data['position']}
Section: {request_data['section']}
Extension: (To be assigned)

Please create a new VOIP user account in the PBX system with the following details:
- Display Name: {request_data['full_name']}
- Email: {request_data.get('work_email') or request_data.get('google_user_email') or request_data['personal_email']}
- Mobile: {request_data.get('phone_mobile', 'N/A')}

Once completed, please update this ticket with the assigned extension number and mark it as solved.

---
Automated request from Oscar (Staff Onboarding Bot)
"""

            response = requests.post(
                f"{self._get_bot_url('sadie')}/api/tickets",
                json={
                    'subject': f"VOIP Setup Required: {request_data['full_name']}",
                    'description': description,
                    'priority': 'normal',
                    'type': 'task'
                },
                headers={'X-API-Key': config.bot_api_key},
                timeout=30
            )

            if response.status_code in [200, 201]:
                result = response.json()
                return {
                    'success': True,
                    'data': {
                        'ticket_id': result.get('ticket', {}).get('id'),
                        'ticket_url': result.get('ticket', {}).get('url'),
                        'sadie_response': result
                    }
                }
            else:
                return {
                    'success': False,
                    'error': f"Sadie API error: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {'success': False, 'error': f'Failed to call Sadie: {str(e)}'}


# Global orchestrator instance (normal mode)
orchestrator = OnboardingOrchestrator(dry_run=False)

# Factory function for creating orchestrators with specific modes
def get_orchestrator(dry_run: bool = False) -> OnboardingOrchestrator:
    """
    Get an orchestrator instance.

    Args:
        dry_run: If True, returns an orchestrator that won't make real API calls

    Returns:
        OnboardingOrchestrator instance
    """
    if dry_run:
        return OnboardingOrchestrator(dry_run=True)
    return orchestrator
