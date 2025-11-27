"""API routes for Evelyn - Excel processing endpoints."""
import io
import logging
from flask import Blueprint, request, jsonify, send_file
from shared.auth.bot_api import api_or_session_auth
from services.excel import excel_service

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


@api_bp.route('/process', methods=['POST'])
@api_or_session_auth
def process_workbook():
    """
    Process an Excel workbook: keep only specified sheets and convert to values.

    Expects multipart form data with:
    - 'file': The Excel file
    - 'sheets': Comma-separated list of sheet names to keep, OR JSON array

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

    # Get sheets to keep
    sheets_param = request.form.get('sheets', '')
    if not sheets_param:
        return jsonify({'error': 'No sheets specified'}), 400

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
