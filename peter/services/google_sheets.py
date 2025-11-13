from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config import config
import os
import re

class GoogleSheetsService:
    """Service for interacting with Google Sheets API"""

    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

    def __init__(self):
        self.credentials = None
        self.service = None
        self._initialize()

    def _initialize(self):
        """Initialize Google Sheets API credentials and service"""
        try:
            if not os.path.exists(config.google_credentials_file):
                print(f"Warning: Credentials file not found at {config.google_credentials_file}")
                return

            # Create credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                config.google_credentials_file,
                scopes=self.SCOPES
            )

            # Build the Sheets API service
            self.service = build('sheets', 'v4', credentials=self.credentials)

        except Exception as e:
            print(f"Error initializing Google Sheets service: {e}")
            import traceback
            traceback.print_exc()
            self.service = None

    def get_all_contacts(self):
        """
        Get all contacts from the phone list

        Returns:
            List of contact dictionaries organized by section
        """
        if not self.service:
            return {'error': 'Google Sheets service not initialized'}

        try:
            # Read all data from the sheet
            range_name = f"{config.sheet_name}!A:E"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=config.spreadsheet_id,
                range=range_name
            ).execute()

            rows = result.get('values', [])

            if not rows:
                return []

            # Parse rows into contacts and sections
            contacts = []
            current_section = None
            row_index = 0

            for row in rows:
                row_index += 1

                # Skip completely empty rows
                if not any(row):
                    continue

                # Pad row to 5 columns
                while len(row) < 5:
                    row.append('')

                extension, name, fixed, mobile, email = row[:5]

                # Check if this is a section header (no extension, name in ALL CAPS spanning columns)
                if not extension and name and name.isupper():
                    # Extract section name and optional phone
                    if ' - ' in name:
                        section_name, section_phone = name.split(' - ', 1)
                        current_section = {
                            'name': section_name.strip(),
                            'phone': section_phone.strip()
                        }
                    else:
                        current_section = {
                            'name': name.strip(),
                            'phone': None
                        }
                    continue

                # Skip if no name (empty row or header row)
                if not name:
                    continue

                # This is a contact row
                contact = {
                    'row': row_index,
                    'extension': extension.strip() if extension else '',
                    'name': name.strip(),
                    'fixed_line': fixed.strip() if fixed else '',
                    'mobile': mobile.strip() if mobile else '',
                    'email': email.strip() if email else '',
                    'section': current_section['name'] if current_section else 'Unknown'
                }

                contacts.append(contact)

            return contacts

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': f'Unexpected error: {e}'}

    def search_contacts(self, query):
        """
        Search for contacts by name, extension, or phone number

        Args:
            query: Search string

        Returns:
            List of matching contact dictionaries
        """
        all_contacts = self.get_all_contacts()

        if isinstance(all_contacts, dict) and 'error' in all_contacts:
            return all_contacts

        query_lower = query.lower()
        results = []

        for contact in all_contacts:
            # Search in name, extension, mobile, fixed_line
            if (query_lower in contact['name'].lower() or
                query_lower in contact['extension'] or
                query_lower in contact['mobile'] or
                query_lower in contact['fixed_line']):
                results.append(contact)

        return results

    def add_contact(self, section, extension, name, fixed_line='', mobile='', email=''):
        """
        Add a new contact to the phone list

        Args:
            section: Section name to add contact under
            extension: 4-digit extension
            name: Contact name
            fixed_line: Fixed line number (optional)
            mobile: Mobile number (optional)
            email: Email address (optional)

        Returns:
            Success message or error
        """
        if not self.service:
            return {'error': 'Google Sheets service not initialized'}

        try:
            # Find the section and determine where to insert
            all_data = self.service.spreadsheets().values().get(
                spreadsheetId=config.spreadsheet_id,
                range=f"{config.sheet_name}!A:E"
            ).execute().get('values', [])

            # Find the section
            section_row = None
            next_section_row = None

            for i, row in enumerate(all_data):
                if len(row) > 1 and not row[0] and row[1].upper() == section.upper():
                    section_row = i
                elif section_row is not None and len(row) > 1 and not row[0] and row[1].isupper():
                    next_section_row = i
                    break

            if section_row is None:
                return {'error': f'Section "{section}" not found'}

            # Determine insert row (end of section or before next section)
            if next_section_row:
                insert_row = next_section_row
            else:
                insert_row = len(all_data)

            # Insert the new contact
            new_row = [[extension, name, fixed_line, mobile, email]]

            result = self.service.spreadsheets().values().update(
                spreadsheetId=config.spreadsheet_id,
                range=f"{config.sheet_name}!A{insert_row + 1}:E{insert_row + 1}",
                valueInputOption='RAW',
                body={'values': new_row}
            ).execute()

            return {
                'success': True,
                'message': f'Added {name} to {section}',
                'row': insert_row + 1
            }

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': f'Unexpected error: {e}'}

    def update_contact(self, row_number, extension='', name='', fixed_line='', mobile='', email=''):
        """
        Update an existing contact

        Args:
            row_number: Row number in the sheet
            extension: New extension (optional, keeps existing if empty)
            name: New name (optional, keeps existing if empty)
            fixed_line: New fixed line (optional, keeps existing if empty)
            mobile: New mobile (optional, keeps existing if empty)
            email: New email (optional, keeps existing if empty)

        Returns:
            Success message or error
        """
        if not self.service:
            return {'error': 'Google Sheets service not initialized'}

        try:
            # Build the update row with only provided values
            update_data = []
            if extension: update_data.append(extension)
            if name: update_data.append(name)
            if fixed_line: update_data.append(fixed_line)
            if mobile: update_data.append(mobile)
            if email: update_data.append(email)

            if not update_data:
                return {'error': 'No fields to update'}

            # Update the row
            result = self.service.spreadsheets().values().update(
                spreadsheetId=config.spreadsheet_id,
                range=f"{config.sheet_name}!A{row_number}:E{row_number}",
                valueInputOption='RAW',
                body={'values': [[extension, name, fixed_line, mobile, email]]}
            ).execute()

            return {
                'success': True,
                'message': f'Updated contact in row {row_number}'
            }

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

    def delete_contact(self, row_number):
        """
        Delete a contact by clearing the row

        Args:
            row_number: Row number to delete

        Returns:
            Success message or error
        """
        if not self.service:
            return {'error': 'Google Sheets service not initialized'}

        try:
            # Clear the row
            result = self.service.spreadsheets().values().clear(
                spreadsheetId=config.spreadsheet_id,
                range=f"{config.sheet_name}!A{row_number}:E{row_number}"
            ).execute()

            return {
                'success': True,
                'message': f'Deleted contact from row {row_number}'
            }

        except HttpError as e:
            return {'error': f'API error: {e}'}
        except Exception as e:
            return {'error': f'Unexpected error: {e}'}

# Singleton instance
sheets_service = GoogleSheetsService()
