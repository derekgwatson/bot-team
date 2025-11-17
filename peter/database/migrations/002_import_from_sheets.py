"""
Import initial data from Google Sheets.

This migration only runs if the staff table is empty, making it safe to
run multiple times or skip if data already exists.
"""

import sys
from pathlib import Path


def up(conn):
    """Import data from Google Sheets if database is empty"""
    cursor = conn.cursor()

    # Check if we already have data
    cursor.execute('SELECT COUNT(*) FROM staff')
    count = cursor.fetchone()[0]

    if count > 0:
        print("  Staff table already has data, skipping import")
        return

    print("  Importing from Google Sheets...")

    try:
        # Import sheets_service only when needed
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from services.sheets_service import sheets_service

        # Get all contacts from Google Sheets
        contacts = sheets_service.get_all_contacts()

        if not contacts:
            print("  No contacts found in Google Sheets")
            return

        # First, collect all unique sections
        unique_sections = set()
        for contact in contacts:
            section = contact.get('section', '').strip()
            if section and section != 'Unknown':
                unique_sections.add(section.title())

        # Add sections
        for i, section_name in enumerate(sorted(unique_sections)):
            cursor.execute(
                'INSERT OR IGNORE INTO sections (name, display_order) VALUES (?, ?)',
                (section_name, i+1)
            )

        # Import staff data
        added = 0
        for contact in contacts:
            name = contact.get('name', '').strip()
            if not name:
                continue

            section = contact.get('section', '').strip()
            section = section.title() if section else ''

            cursor.execute('''
                INSERT INTO staff (
                    name, position, section, extension, phone_fixed, phone_mobile,
                    work_email, personal_email, show_on_phone_list, include_in_allstaff,
                    zendesk_access, google_access, wiki_access,
                    created_by, modified_by, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                contact.get('position', ''),
                section,
                contact.get('extension', ''),
                contact.get('fixed_line', ''),
                contact.get('mobile', ''),
                contact.get('email', ''),
                '',  # personal_email
                True,  # show_on_phone_list
                True,  # include_in_allstaff
                bool(contact.get('email')),  # zendesk_access
                bool(contact.get('email')),  # google_access
                bool(contact.get('email')),  # wiki_access
                'auto-migration',
                'auto-migration',
                f"Migrated from Google Sheets on {contact.get('last_updated', 'unknown date')}"
            ))
            added += 1

        print(f"  Imported {added} staff members and {len(unique_sections)} sections")

    except Exception as e:
        print(f"  Warning: Could not import from Google Sheets: {e}")
        print(f"  This is OK - you can add staff manually or the database may be in a different environment")


def down(conn):
    """Clear imported data"""
    cursor = conn.cursor()
    cursor.execute('DELETE FROM staff WHERE created_by = ?', ('auto-migration',))
    cursor.execute('DELETE FROM sections')
