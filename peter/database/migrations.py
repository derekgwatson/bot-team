"""
Auto-migration system for Peter's database

This runs automatically on app startup to ensure the database is populated.
If the staff table is empty, it will automatically import from Google Sheets.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import staff_db
from services.sheets_service import sheets_service


def needs_migration():
    """Check if database needs initial data migration"""
    try:
        staff = staff_db.get_all_staff(status='all')
        return len(staff) == 0
    except Exception as e:
        print(f"Error checking migration status: {e}")
        return False


def auto_migrate():
    """
    Automatically migrate data from Google Sheets if database is empty.
    This is safe to run multiple times - it only migrates if needed.
    """
    if not needs_migration():
        print("✓ Database already populated, skipping migration")
        return True

    print("\n" + "="*60)
    print("📦 Auto-Migration: Database is empty")
    print("   Importing staff data from Google Sheets...")
    print("="*60)

    try:
        # Get all contacts from Google Sheets
        contacts = sheets_service.get_all_contacts()

        if not contacts:
            print("⚠️  No contacts found in Google Sheets")
            print("   Database will remain empty")
            return True

        print(f"Found {len(contacts)} contacts in Google Sheets")
        print()

        # First, collect all unique sections and add them to the sections table
        print("Populating sections table...")
        unique_sections = set()
        for contact in contacts:
            section = contact.get('section', '').strip()
            if section and section != 'Unknown':
                unique_sections.add(section.title())

        sections_added = 0
        for i, section_name in enumerate(sorted(unique_sections)):
            result = staff_db.add_section(name=section_name, display_order=i+1)
            if 'success' in result:
                sections_added += 1

        print(f"  ✓ Added {sections_added} sections")
        print()

        # Now migrate staff data
        print("Migrating staff data...")
        added = 0
        skipped = 0
        errors = []

        for contact in contacts:
            name = contact.get('name', '').strip()

            if not name:
                skipped += 1
                continue

            # Map old field names to new
            staff_data = {
                'name': name,
                'position': contact.get('position', ''),
                'section': contact.get('section', '').strip().title() if contact.get('section', '').strip() else '',
                'extension': contact.get('extension', ''),
                'phone_fixed': contact.get('fixed_line', ''),
                'phone_mobile': contact.get('mobile', ''),
                'work_email': contact.get('email', ''),
                'personal_email': '',  # Not in old sheet
                'show_on_phone_list': True,  # Default to visible
                'include_in_allstaff': True,  # Default to included
                'created_by': 'auto-migration',
                'modified_by': 'auto-migration',
                'notes': f"Migrated from Google Sheets on {contact.get('last_updated', 'unknown date')}"
            }

            # Set access flags based on available data
            # You can customize this logic based on your needs
            staff_data['zendesk_access'] = bool(staff_data['work_email'])
            staff_data['google_access'] = bool(staff_data['work_email'])
            staff_data['wiki_access'] = bool(staff_data['work_email'])

            result = staff_db.add_staff(**staff_data)

            if 'success' in result:
                added += 1
            else:
                errors.append(f"{name}: {result.get('error', 'Unknown error')}")

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
            for error in errors[:5]:  # Show first 5 errors
                print(f"  - {error}")
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more")

        print()
        print("✓ Auto-migration complete!")
        print("="*60 + "\n")

        return True

    except Exception as e:
        print(f"\n✗ Auto-migration failed: {e}")
        print("  The app will continue, but database will be empty")
        print("  You can manually run: python database/migrate_from_sheets.py")
        print()
        return False


if __name__ == '__main__':
    """Can also be run standalone for manual migration"""
    success = auto_migrate()
    sys.exit(0 if success else 1)
