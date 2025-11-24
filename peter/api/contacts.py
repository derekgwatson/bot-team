from flask import Blueprint, jsonify, request
from database.db import staff_db

api_bp = Blueprint('api', __name__)

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    GET /api/intro

    Returns Peter's introduction
    """
    return jsonify({
        'name': 'Peter',
        'greeting': "Hi! I'm Peter, your staff directory.",
        'description': "I keep track of all your staff - their contact details, what systems they can access, who should be on the phone list, and who's in the all-staff email group. Need to find someone's mobile? Want to know who has Zendesk access? Just ask me!",
        'capabilities': [
            'Keep track of all staff contact information',
            'Track system access (Zendesk, Buz, Google, Wiki, VOIP)',
            'Manage who appears on the phone list',
            'Manage who\'s in the all-staff email group',
            'Search for staff by name, extension, or phone',
            'Add, update, and manage staff information',
            'API for other bots to access staff info'
        ]
    })

@api_bp.route('/contacts', methods=['GET'])
def get_contacts():
    """
    GET /api/contacts

    Returns contacts that should appear on the phone list
    (for backward compatibility with Pam)
    """
    try:
        contacts = staff_db.get_phone_list_staff()

        # Convert to old format for compatibility
        formatted = []
        for staff in contacts:
            formatted.append({
                'row': staff['id'],
                'extension': staff['extension'],
                'name': staff['name'],
                'position': staff['position'],
                'fixed_line': staff['phone_fixed'],
                'mobile': staff['phone_mobile'],
                'email': staff['work_email'],
                'section': staff['section']
            })

        return jsonify({
            'contacts': formatted,
            'count': len(formatted)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/contacts/search', methods=['GET'])
def search_contacts():
    """
    GET /api/contacts/search?q=query

    Search for contacts
    """
    query = request.args.get('q', '')

    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    try:
        results = staff_db.search_staff(query)

        # Convert to old format for compatibility
        formatted = []
        for staff in results:
            formatted.append({
                'row': staff['id'],
                'extension': staff['extension'],
                'name': staff['name'],
                'position': staff['position'],
                'fixed_line': staff['phone_fixed'],
                'mobile': staff['phone_mobile'],
                'email': staff['work_email'],
                'section': staff['section']
            })

        return jsonify({
            'results': formatted,
            'count': len(formatted),
            'query': query
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/contacts', methods=['POST'])
def add_contact():
    """
    POST /api/contacts

    Body (JSON):
        {
            "name": "John Doe",
            "position": "Sales Manager",
            "section": "SALES",
            "extension": "1234",
            "phone_fixed": "02 1234 5678",
            "phone_mobile": "0412 345 678",
            "work_email": "john@watsonblinds.com.au",
            "personal_email": "john@gmail.com",
            "show_on_phone_list": true,
            "include_in_allstaff": true
        }

    Adds a new staff member
    """
    data = request.get_json()

    # Validate required fields
    if 'name' not in data:
        return jsonify({'error': 'name is required'}), 400

    result = staff_db.add_staff(
        name=data['name'],
        position=data.get('position', ''),
        section=data.get('section', ''),
        extension=data.get('extension', ''),
        phone_fixed=data.get('phone_fixed', data.get('fixed_line', '')),  # Support old field name
        phone_mobile=data.get('phone_mobile', data.get('mobile', '')),  # Support old field name
        work_email=data.get('work_email', data.get('email', '')),  # Support old field name
        personal_email=data.get('personal_email', ''),
        show_on_phone_list=data.get('show_on_phone_list', True),
        include_in_allstaff=data.get('include_in_allstaff', True),
        created_by=data.get('created_by', 'api')
    )

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result), 201

@api_bp.route('/contacts/<int:staff_id>', methods=['PUT'])
def update_contact(staff_id):
    """
    PUT /api/contacts/<staff_id>

    Updates a staff member
    """
    data = request.get_json()

    # Map old field names to new ones
    update_data = {}
    field_mapping = {
        'fixed_line': 'phone_fixed',
        'mobile': 'phone_mobile',
        'email': 'work_email'
    }

    for key, value in data.items():
        # Map old field names
        if key in field_mapping:
            update_data[field_mapping[key]] = value
        else:
            update_data[key] = value

    result = staff_db.update_staff(
        staff_id=staff_id,
        modified_by=data.get('modified_by', 'api'),
        **update_data
    )

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)

@api_bp.route('/contacts/<int:staff_id>', methods=['DELETE'])
def delete_contact(staff_id):
    """
    DELETE /api/contacts/<staff_id>

    Deletes a staff member (sets status to inactive)
    """
    result = staff_db.delete_staff(staff_id)

    if 'error' in result:
        return jsonify(result), 400

    return jsonify(result)


# New staff-focused endpoints

@api_bp.route('/staff', methods=['GET'])
def get_all_staff():
    """
    GET /api/staff?status=active

    Returns all staff members (not filtered by phone list)
    """
    status = request.args.get('status', 'active')
    name = request.args.get('name')

    try:
        if name:
            # Search by name
            staff = staff_db.search_staff(name)
        else:
            staff = staff_db.get_all_staff(status=status)

        return jsonify({
            'staff': staff,
            'count': len(staff)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/staff', methods=['POST'])
def create_staff():
    """
    POST /api/staff

    Creates a new staff member
    Used by Oscar onboarding bot and other automation
    """
    try:
        data = request.get_json()

        # Validate required fields
        if 'name' not in data:
            return jsonify({'error': 'name is required'}), 400

        result = staff_db.add_staff(
            name=data['name'],
            position=data.get('position', ''),
            section=data.get('section', ''),
            extension=data.get('extension', ''),
            phone_fixed=data.get('phone_fixed', ''),
            phone_mobile=data.get('phone_mobile', ''),
            work_email=data.get('work_email', ''),
            personal_email=data.get('personal_email', ''),
            google_primary_email=data.get('google_primary_email', ''),
            zendesk_access=data.get('zendesk_access', False),
            buz_access=data.get('buz_access', False),
            google_access=data.get('google_access', False),
            wiki_access=data.get('wiki_access', False),
            voip_access=data.get('voip_access', False),
            show_on_phone_list=data.get('show_on_phone_list', True),
            include_in_allstaff=data.get('include_in_allstaff', True),
            status=data.get('status', 'active'),
            notes=data.get('notes', ''),
            created_by=data.get('created_by', 'api')
        )

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/staff/<int:staff_id>', methods=['GET'])
def get_staff(staff_id):
    """
    GET /api/staff/<staff_id>

    Returns a specific staff member
    """
    try:
        staff = staff_db.get_staff_by_id(staff_id)
        if not staff:
            return jsonify({'error': 'Staff member not found'}), 404

        return jsonify(staff)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/staff/<int:staff_id>', methods=['PATCH'])
def update_staff(staff_id):
    """
    PATCH /api/staff/<staff_id>

    Updates specific fields for a staff member
    Commonly used by Olive offboarding bot to set finish_date and status
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Check if staff exists
        staff = staff_db.get_staff_by_id(staff_id)
        if not staff:
            return jsonify({'error': 'Staff member not found'}), 404

        # Update the staff member
        result = staff_db.update_staff(
            staff_id=staff_id,
            modified_by=data.get('modified_by', 'api'),
            **{k: v for k, v in data.items() if k != 'modified_by'}
        )

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/staff/allstaff-members', methods=['GET'])
def get_allstaff_members():
    """
    GET /api/staff/allstaff-members

    Returns email addresses for all-staff group
    (This is what Quinn will call to sync the Google Group)
    """
    try:
        emails = staff_db.get_allstaff_members()
        return jsonify({
            'emails': emails,
            'count': len(emails)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Access Request Endpoints

@api_bp.route('/access-requests', methods=['POST'])
def submit_access_request():
    """
    POST /api/access-requests

    Submit a new access request (public endpoint for external staff)

    Body:
        name: Person's name (required)
        email: Personal email address (required)
        phone: Phone number (optional)
        reason: Reason for access request (optional)
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body is required'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    reason = data.get('reason', '').strip()

    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400

    try:
        result = staff_db.submit_access_request(name, email, phone, reason)

        if 'error' in result:
            status_code = 400 if result.get('already_approved') or result.get('already_pending') else 500
            return jsonify(result), status_code

        return jsonify(result), 201

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access-requests', methods=['GET'])
def get_access_requests():
    """
    GET /api/access-requests?status=pending

    Get access requests (admin only)

    Query params:
        status: Filter by status ('pending', 'approved', 'denied', or omit for all)
    """
    status = request.args.get('status', 'pending')
    if status == 'all':
        status = None

    try:
        requests = staff_db.get_access_requests(status=status)
        return jsonify({
            'requests': requests,
            'count': len(requests)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access-requests/<int:request_id>', methods=['GET'])
def get_access_request(request_id):
    """
    GET /api/access-requests/<request_id>

    Get a specific access request
    """
    try:
        access_request = staff_db.get_access_request_by_id(request_id)
        if not access_request:
            return jsonify({'error': 'Access request not found'}), 404

        return jsonify(access_request)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access-requests/<int:request_id>/approve', methods=['POST'])
def approve_access_request(request_id):
    """
    POST /api/access-requests/<request_id>/approve

    Approve an access request (admin only)

    Body:
        reviewed_by: Email of person approving (required)
        create_staff: Whether to create staff entry (optional, default true)
    """
    data = request.get_json() or {}
    reviewed_by = data.get('reviewed_by')

    if not reviewed_by:
        return jsonify({'error': 'reviewed_by is required'}), 400

    create_staff = data.get('create_staff', True)

    try:
        result = staff_db.approve_access_request(request_id, reviewed_by, create_staff)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/access-requests/<int:request_id>/deny', methods=['POST'])
def deny_access_request(request_id):
    """
    POST /api/access-requests/<request_id>/deny

    Deny an access request (admin only)

    Body:
        reviewed_by: Email of person denying (required)
        notes: Reason for denial (optional)
    """
    data = request.get_json() or {}
    reviewed_by = data.get('reviewed_by')
    notes = data.get('notes', '')

    if not reviewed_by:
        return jsonify({'error': 'reviewed_by is required'}), 400

    try:
        result = staff_db.deny_access_request(request_id, reviewed_by, notes)

        if 'error' in result:
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/is-approved', methods=['GET'])
def is_approved():
    """
    GET /api/is-approved?email=someone@example.com

    Check if an email is approved for access
    (For other bots like Pam to check external staff access)

    Checks all email fields: google_primary_email, work_email, and personal_email.
    This handles the case where a user logs in with their Google primary email
    but their work_email in Peter is set to an alias.

    Returns:
        approved: boolean
        name: staff name (if approved)
        email: email address
    """
    email = request.args.get('email', '').strip()

    if not email:
        return jsonify({'error': 'email parameter is required'}), 400

    try:
        # Search for staff by any email (google_primary_email, work, or personal)
        staff = staff_db.get_staff_by_email(email)

        if staff:
            return jsonify({
                'approved': True,
                'name': staff['name'],
                'email': email
            })
        else:
            return jsonify({
                'approved': False,
                'email': email
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500
