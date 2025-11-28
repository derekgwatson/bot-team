"""
Migration: Add home_org field to inventory_groups.

Each inventory group has a "home org" (typically Canberra or DD) that contains
the authoritative/complete set of items. Other orgs get items copied on-demand
during the ordering process. This field tracks which org is the source of truth
for each group.
"""


def up(conn):
    """Add home_org column to inventory_groups."""
    conn.execute('''
        ALTER TABLE inventory_groups
        ADD COLUMN home_org TEXT
    ''')


def down(conn):
    """Remove home_org column (SQLite doesn't support DROP COLUMN easily)."""
    # SQLite doesn't support DROP COLUMN, would need to recreate table
    pass
