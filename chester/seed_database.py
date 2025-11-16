#!/usr/bin/env python3
"""Seed the Chester database with initial bot data."""
from services.database import db

# Bot deployment data from Dorothy's config.local.yaml
bots_data = [
    {
        'name': 'fred',
        'description': 'Google Workspace User Management',
        'port': 8001
    },
    {
        'name': 'iris',
        'description': 'Google Workspace Reporting & Analytics',
        'port': 8002
    },
    {
        'name': 'peter',
        'description': 'Phone Directory Manager',
        'port': 8003
    },
    {
        'name': 'sally',
        'description': 'SSH Command Executor',
        'port': 8004,
        'skip_nginx': True  # Internal-only bot
    },
    {
        'name': 'dorothy',
        'description': 'Deployment Orchestrator',
        'port': 8005
    },
    {
        'name': 'quinn',
        'description': 'External Staff Access Manager',
        'port': 8006
    },
    {
        'name': 'zac',
        'description': 'Zendesk User Manager',
        'port': 8007
    },
    {
        'name': 'sadie',
        'description': 'Zendesk Ticket Information',
        'port': 8010
    },
    {
        'name': 'chester',
        'description': 'Bot Team Concierge',
        'port': 8008
    },
    {
        'name': 'pam',
        'description': 'Phone Directory Presenter',
        'port': 8009
    }
]


def seed_database():
    """Seed the database with initial bot data."""
    print("Seeding Chester database...")

    for bot_data in bots_data:
        name = bot_data['name']

        # Check if bot already exists
        existing = db.get_bot(name)
        if existing:
            print(f"  ✓ {name} already exists, skipping...")
            continue

        try:
            bot_id = db.add_bot(**bot_data)
            if bot_id:
                print(f"  ✓ Added {name} (ID: {bot_id})")
            else:
                print(f"  ✗ Failed to add {name}")
        except Exception as e:
            print(f"  ✗ Error adding {name}: {e}")

    print("\nDatabase seeding complete!")
    print(f"\nTotal bots in database: {len(db.get_all_bots())}")


if __name__ == '__main__':
    seed_database()
