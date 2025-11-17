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

    try:
        staff = staff_db.get_all_staff(status=status)
        return jsonify({
            'staff': staff,
            'count': len(staff)
        })
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
