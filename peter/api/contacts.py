from flask import Blueprint, jsonify, request
from services.google_sheets import sheets_service

api_bp = Blueprint('api', __name__)

@api_bp.route('/intro', methods=['GET'])
def intro():
    """
    GET /api/intro

    Returns Peter's introduction
    """
    return jsonify({
        'name': 'Peter',
        'greeting': "Hi! I'm Peter, your phone directory manager.",
        'description': "I keep track of everyone's phone numbers and extensions in your organization. Need to find someone's mobile? Want to know who has extension 1234? Just ask me! I sync with your Google Sheet phone list and make it easy to search, add, or update contacts.",
        'capabilities': [
            'List all contacts in the phone directory',
            'Search for contacts by name, extension, or phone number',
            'Add new contacts to the directory',
            'Update existing contact information',
            'Delete contacts from the directory',
            'Organize contacts by department/section',
            'REST API for bot-to-bot integration'
        ]
    })

@api_bp.route('/contacts', methods=['GET'])
def get_contacts():
    """
    GET /api/contacts

    Returns all contacts from the phone directory
    """
    contacts = sheets_service.get_all_contacts()

    if isinstance(contacts, dict) and 'error' in contacts:
        return jsonify(contacts), 500

    return jsonify({
        'contacts': contacts,
        'count': len(contacts)
    })

@api_bp.route('/contacts/search', methods=['GET'])
def search_contacts():
    """
    GET /api/contacts/search?q=query

    Search for contacts
    """
    query = request.args.get('q', '')

    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    results = sheets_service.search_contacts(query)

    if isinstance(results, dict) and 'error' in results:
        return jsonify(results), 500

    return jsonify({
        'results': results,
        'count': len(results),
        'query': query
    })

@api_bp.route('/contacts', methods=['POST'])
def add_contact():
    """
    POST /api/contacts

    Body (JSON):
        {
            "section": "SALES",
            "extension": "1234",
            "name": "John Doe",
            "fixed_line": "02 1234 5678",
            "mobile": "0412 345 678",
            "email": "john@example.com"
        }

    Adds a new contact
    """
    data = request.get_json()

    # Validate required fields
    if 'section' not in data or 'name' not in data:
        return jsonify({'error': 'section and name are required'}), 400

    result = sheets_service.add_contact(
        section=data['section'],
        extension=data.get('extension', ''),
        name=data['name'],
        fixed_line=data.get('fixed_line', ''),
        mobile=data.get('mobile', ''),
        email=data.get('email', '')
    )

    if isinstance(result, dict) and 'error' in result:
        return jsonify(result), 500

    return jsonify(result), 201

@api_bp.route('/contacts/<int:row>', methods=['PUT'])
def update_contact(row):
    """
    PUT /api/contacts/<row>

    Updates a contact at the specified row
    """
    data = request.get_json()

    result = sheets_service.update_contact(
        row_number=row,
        extension=data.get('extension', ''),
        name=data.get('name', ''),
        fixed_line=data.get('fixed_line', ''),
        mobile=data.get('mobile', ''),
        email=data.get('email', '')
    )

    if isinstance(result, dict) and 'error' in result:
        return jsonify(result), 500

    return jsonify(result)

@api_bp.route('/contacts/<int:row>', methods=['DELETE'])
def delete_contact(row):
    """
    DELETE /api/contacts/<row>

    Deletes a contact at the specified row
    """
    result = sheets_service.delete_contact(row)

    if isinstance(result, dict) and 'error' in result:
        return jsonify(result), 500

    return jsonify(result)
