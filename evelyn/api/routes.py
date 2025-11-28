"""API routes for Evelyn - Excel processing endpoints."""
import io
import logging
from flask import Blueprint, request, jsonify, send_file
from shared.auth.bot_api import api_or_session_auth
from services.excel import excel_service
from config import config

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)


@api_bp.route('/sheets', methods=['POST'])
@api_or_session_auth
def get_sheets():
    """
    Get list of sheet names from an uploaded Excel workbook.

    Expects multipart form data with 'file' field.

    Returns:
        JSON with list of sheet names
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith(('.xlsx', '.xlsm')):
        return jsonify({'error': 'File must be an Excel file (.xlsx or .xlsm)'}), 400

    try:
        # Read file into memory
        file_data = io.BytesIO(file.read())
        sheet_names = excel_service.get_sheet_names(file_data)

        return jsonify({
            'success': True,
            'filename': file.filename,
            'sheets': sheet_names
        })

    except Exception as e:
        logger.exception(f"Error reading Excel file: {e}")
        return jsonify({'error': f'Error reading Excel file: {str(e)}'}), 400


@api_bp.route('/profiles', methods=['GET'])
@api_or_session_auth
def list_profiles():
    """
    List available sheet profiles.

    Returns:
        JSON with available profiles and their configurations
    """
    profiles = config.list_profiles()
    return jsonify({
        'success': True,
        'profiles': profiles
    })


@api_bp.route('/process', methods=['POST'])
@api_or_session_auth
def process_workbook():
    """
    Process an Excel workbook: keep only specified sheets and convert to values.

    Expects multipart form data with:
    - 'file': The Excel file
    - 'sheets': Comma-separated list of sheet names to keep, OR JSON array
    - 'profile': (Alternative to sheets) Name of a predefined profile from config

    If both 'profile' and 'sheets' are provided, 'profile' takes precedence.

    Returns:
        The processed Excel file as a download
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not file.filename.endswith(('.xlsx', '.xlsm')):
        return jsonify({'error': 'File must be an Excel file (.xlsx or .xlsm)'}), 400

    # Check for profile first
    profile_name = request.form.get('profile', '').strip()
    filename_suffix = '_processed'  # Default suffix

    if profile_name:
        profile = config.get_profile(profile_name)
        if not profile:
            available = list(config.list_profiles().keys())
            return jsonify({
                'error': f"Profile '{profile_name}' not found",
                'available_profiles': available
            }), 400
        sheets_to_keep = profile.get('sheets', [])
        filename_suffix = profile.get('filename_suffix', '_processed')
        logger.info(f"Using profile '{profile_name}': sheets={sheets_to_keep}")
    else:
        # Get sheets to keep from parameter
        sheets_param = request.form.get('sheets', '')
        if not sheets_param:
            return jsonify({'error': 'No sheets or profile specified'}), 400

        # Parse sheets - could be comma-separated or JSON array
        if sheets_param.startswith('['):
            import json
            try:
                sheets_to_keep = json.loads(sheets_param)
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid sheets JSON'}), 400
        else:
            sheets_to_keep = [s.strip() for s in sheets_param.split(',') if s.strip()]

    if not sheets_to_keep:
        return jsonify({'error': 'No sheets specified'}), 400

    try:
        # Read file into memory
        file_data = io.BytesIO(file.read())

        # Process the workbook
        output, output_filename = excel_service.process_workbook(
            file_data,
            sheets_to_keep,
            file.filename
        )

        # Apply custom suffix if from profile
        if filename_suffix != '_processed':
            base_name = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
            output_filename = f"{base_name}{filename_suffix}.xlsx"

        logger.info(f"Processed {file.filename} -> {output_filename}, kept sheets: {sheets_to_keep}")

        # Return the processed file
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=output_filename
        )

    except ValueError as e:
        # Sheet not found or similar validation error
        return jsonify({'error': str(e)}), 400

    except Exception as e:
        logger.exception(f"Error processing Excel file: {e}")
        return jsonify({'error': f'Error processing Excel file: {str(e)}'}), 500
