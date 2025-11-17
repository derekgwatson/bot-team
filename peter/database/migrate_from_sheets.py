#!/usr/bin/env python3
"""
Migration script to seed Peter's database from Google Sheets

This script reads the existing Google Sheets phone list and populates
the new SQLite database with all staff information.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.google_sheets import sheets_service
from database.db import staff_db

def migrate():
    """Migrate data from Google Sheets to SQLite"""
    print("Starting migration from Google Sheets to SQLite...")
    print("-" * 60)

    # Get all contacts from Google Sheets
    print("Fetching contacts from Google Sheets...")
    contacts = sheets_service.get_all_contacts()

    if isinstance(contacts, dict) and 'error' in contacts:
        print(f"ERROR: {contacts['error']}")
        return False

    print(f"Found {len(contacts)} contacts in Google Sheets")
    print()

    # Track migration stats
    added = 0
    skipped = 0
    errors = []

    # Migrate each contact
    for contact in contacts:
        name = contact.get('name', '').strip()
        if not name:
            skipped += 1
            continue

        # Determine if they should be in allstaff (if they have an email)
        work_email = contact.get('email', '').strip()
        include_in_allstaff = bool(work_email)

        # Add to database with sensible defaults
        result = staff_db.add_staff(
            name=name,
            position=contact.get('position', ''),
            section=contact.get('section', 'Unknown'),
            extension=contact.get('extension', ''),
            phone_fixed=contact.get('fixed_line', ''),
            phone_mobile=contact.get('mobile', ''),
            work_email=work_email,
            personal_email='',  # Will be filled in later
            # Access flags - set to False initially, will be configured later
            zendesk_access=False,
            buz_access=False,
            google_access=bool(work_email),  # Assume Google access if they have email
            wiki_access=False,
            voip_access=bool(contact.get('extension', '')),  # Assume VOIP if they have extension
            # Display flags
            show_on_phone_list=True,  # Everyone currently on the sheet should be shown
            include_in_allstaff=include_in_allstaff,
            created_by='migration_script',
            notes=f"Migrated from Google Sheets (row {contact.get('row', 'unknown')})"
        )

        if 'error' in result:
            errors.append(f"{name}: {result['error']}")
        else:
            added += 1
            print(f"✓ Added: {name} ({contact.get('section', 'Unknown')})")

    # Print summary
    print()
    print("-" * 60)
    print("Migration Summary:")
    print(f"  Total contacts in sheet: {len(contacts)}")
    print(f"  Successfully added:      {added}")
    print(f"  Skipped (no name):       {skipped}")
    print(f"  Errors:                  {len(errors)}")

    if errors:
        print()
        print("Errors:")
        for error in errors:
            print(f"  - {error}")

    print()
    print("Migration complete!")
    print()
    print("NEXT STEPS:")
    print("1. Review the migrated data and update access flags as needed")
    print("2. Add personal email addresses for staff without work emails")
    print("3. Configure show_on_phone_list and include_in_allstaff flags")
    print("4. Test Peter's new API endpoints")

    return True

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
