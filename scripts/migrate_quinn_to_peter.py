#!/usr/bin/env python3
"""
Migrate external staff data from Quinn to Peter.

This script reads all external staff from Quinn's database and adds them to Peter's
database, making Peter the single source of truth for ALL staff.

Usage:
    # Dry run (see what would happen)
    python migrate_quinn_to_peter.py --dry-run

    # Actually migrate
    python migrate_quinn_to_peter.py

    # Migrate and mark as show on phone list
    python migrate_quinn_to_peter.py --show-on-phone-list
"""

import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime


def get_quinn_staff(quinn_db_path):
    """Get all active external staff from Quinn's database."""
    try:
        conn = sqlite3.connect(quinn_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM external_staff WHERE status = 'active' ORDER BY name"
        )
        staff = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return staff
    except sqlite3.OperationalError as e:
        print(f"❌ Error reading Quinn's database: {e}")
        print(f"   Make sure {quinn_db_path} exists")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []


def check_duplicate_in_peter(peter_db_path, email):
    """Check if email already exists in Peter's database."""
    try:
        conn = sqlite3.connect(peter_db_path)
        cursor = conn.execute(
            "SELECT id, name FROM staff WHERE work_email = ? OR personal_email = ?",
            (email, email)
        )
        result = cursor.fetchone()
        conn.close()
        return result
    except:
        return None


def migrate_to_peter(peter_db_path, quinn_staff, dry_run=False, show_on_phone_list=False):
    """Migrate Quinn's staff to Peter's database."""

    migrated = []
    skipped = []
    errors = []

    for person in quinn_staff:
        name = person['name']
        email = person['email']
        phone = person.get('phone', '')
        role = person.get('role', '')
        notes = person.get('notes', '')
        added_by = person.get('added_by', 'quinn-migration')

        # Check for duplicates
        duplicate = check_duplicate_in_peter(peter_db_path, email)
        if duplicate:
            skipped.append({
                'name': name,
                'email': email,
                'reason': f'Already exists in Peter as "{duplicate[1]}" (ID: {duplicate[0]})'
            })
            continue

        if dry_run:
            migrated.append({
                'name': name,
                'email': email,
                'phone': phone,
                'role': role
            })
        else:
            try:
                # Add to Peter's database
                conn = sqlite3.connect(peter_db_path)

                # Build notes with original info from Quinn
                migration_notes = f"Migrated from Quinn on {datetime.now().strftime('%Y-%m-%d')}."
                if role:
                    migration_notes += f" Role: {role}."
                if notes:
                    migration_notes += f" Original notes: {notes}"

                cursor = conn.execute(
                    '''INSERT INTO staff
                       (name, personal_email, phone_mobile, status, include_in_allstaff,
                        show_on_phone_list, created_by, modified_by, notes)
                       VALUES (?, ?, ?, 'active', 1, ?, ?, ?, ?)''',
                    (
                        name,
                        email,
                        phone,
                        1 if show_on_phone_list else 0,
                        added_by,
                        added_by,
                        migration_notes
                    )
                )
                staff_id = cursor.lastrowid
                conn.commit()
                conn.close()

                migrated.append({
                    'id': staff_id,
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'role': role
                })

            except Exception as e:
                errors.append({
                    'name': name,
                    'email': email,
                    'error': str(e)
                })

    return migrated, skipped, errors


def main():
    parser = argparse.ArgumentParser(
        description='Migrate external staff from Quinn to Peter'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be migrated without actually doing it'
    )
    parser.add_argument(
        '--show-on-phone-list',
        action='store_true',
        help='Mark migrated staff as visible on phone list (default: hidden)'
    )
    parser.add_argument(
        '--quinn-db',
        default='quinn/database/external_staff.db',
        help='Path to Quinn database (default: quinn/database/external_staff.db)'
    )
    parser.add_argument(
        '--peter-db',
        default='peter/database/staff.db',
        help='Path to Peter database (default: peter/database/staff.db)'
    )

    args = parser.parse_args()

    # Resolve paths relative to bot-team root
    script_dir = Path(__file__).parent
    bot_team_root = script_dir.parent
    quinn_db_path = bot_team_root / args.quinn_db
    peter_db_path = bot_team_root / args.peter_db

    print("\n" + "="*70)
    print("📦 Quinn to Peter Staff Migration")
    print("="*70)

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")

    print(f"\nQuinn DB: {quinn_db_path}")
    print(f"Peter DB: {peter_db_path}")
    print(f"Show on phone list: {args.show_on_phone_list}")
    print()

    # Check database files exist
    if not quinn_db_path.exists():
        print(f"❌ Quinn database not found: {quinn_db_path}")
        print("   Make sure you're running this from the bot-team directory")
        sys.exit(1)

    if not peter_db_path.exists():
        print(f"❌ Peter database not found: {peter_db_path}")
        print("   Make sure Peter's database is initialized")
        sys.exit(1)

    # Get Quinn's staff
    print("📖 Reading Quinn's database...")
    quinn_staff = get_quinn_staff(quinn_db_path)

    if not quinn_staff:
        print("✅ No active staff found in Quinn's database")
        print("   Migration complete (nothing to migrate)")
        return

    print(f"   Found {len(quinn_staff)} active staff members in Quinn\n")

    # Migrate
    print("🔄 Migrating staff to Peter...")
    migrated, skipped, errors = migrate_to_peter(
        peter_db_path,
        quinn_staff,
        dry_run=args.dry_run,
        show_on_phone_list=args.show_on_phone_list
    )

    print()
    print("="*70)
    print("📊 Migration Summary")
    print("="*70)

    # Show migrated
    if migrated:
        print(f"\n✅ Migrated: {len(migrated)}")
        for person in migrated:
            if args.dry_run:
                print(f"   • {person['name']} ({person['email']})")
                if person['phone']:
                    print(f"     Phone: {person['phone']}")
                if person['role']:
                    print(f"     Role: {person['role']}")
            else:
                print(f"   • {person['name']} ({person['email']}) → Peter ID: {person['id']}")

    # Show skipped
    if skipped:
        print(f"\n⊘ Skipped: {len(skipped)}")
        for person in skipped:
            print(f"   • {person['name']} ({person['email']})")
            print(f"     Reason: {person['reason']}")

    # Show errors
    if errors:
        print(f"\n❌ Errors: {len(errors)}")
        for person in errors:
            print(f"   • {person['name']} ({person['email']})")
            print(f"     Error: {person['error']}")

    print()

    # Final status
    if args.dry_run:
        print("🔍 This was a dry run. No changes were made.")
        print("   Run without --dry-run to actually migrate the data.")
    else:
        if errors:
            print("⚠️  Migration completed with errors. Please review above.")
        else:
            print("✅ Migration completed successfully!")
            print("\nNext steps:")
            print("1. Check Peter's database to verify the migrated staff")
            print("2. Quinn will now sync these staff to the Google Group")
            print("3. You can safely stop using Quinn's staff management UI")

    print()


if __name__ == '__main__':
    main()
