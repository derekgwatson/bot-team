#!/usr/bin/env python3
"""
Script to seed the sections table from existing staff data

This is useful if you already have staff in the database but the sections
table is empty. It will extract all unique sections from the staff table
and add them to the sections table.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import staff_db

def seed_sections():
    """Seed sections table from existing staff data"""
    print("Seeding sections from existing staff data...")
    print("-" * 60)

    # Get all staff (including inactive)
    all_staff = staff_db.get_all_staff(status='all')
    print(f"Found {len(all_staff)} staff members")

    # Extract unique sections
    unique_sections = set()
    for staff in all_staff:
        section = staff.get('section', '').strip()
        if section and section != 'Unknown':
            unique_sections.add(section.title())

    print(f"Found {len(unique_sections)} unique sections: {sorted(unique_sections)}")
    print()

    # Add each section
    added = 0
    already_exist = 0
    errors = []

    for i, section_name in enumerate(sorted(unique_sections)):
        result = staff_db.add_section(name=section_name, display_order=i+1)

        if 'success' in result:
            added += 1
            print(f"✓ Added: {section_name}")
        elif 'error' in result and 'UNIQUE constraint' in str(result['error']):
            already_exist += 1
            print(f"○ Already exists: {section_name}")
        else:
            errors.append(f"{section_name}: {result.get('error', 'Unknown error')}")
            print(f"✗ Error: {section_name}")

    # Print summary
    print()
    print("-" * 60)
    print("Summary:")
    print(f"  Sections added:        {added}")
    print(f"  Already existed:       {already_exist}")
    print(f"  Errors:                {len(errors)}")

    if errors:
        print()
        print("Errors:")
        for error in errors:
            print(f"  - {error}")

    print()
    print("Done! Your sections table is now populated.")
    return True

if __name__ == '__main__':
    success = seed_sections()
    sys.exit(0 if success else 1)
