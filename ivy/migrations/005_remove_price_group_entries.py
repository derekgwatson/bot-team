"""
Migration: Remove pricing entries with price_group_code.

Zips have pricing entries with price_group_code values which we don't use.
This migration deletes them to clean up the database. Future syncs will
skip these entries during parsing.
"""


def up(conn):
    """Delete pricing entries that have a non-empty price_group_code."""
    conn.execute('''
        DELETE FROM pricing_coefficients
        WHERE price_group_code IS NOT NULL AND price_group_code != ''
    ''')


def down(conn):
    """Cannot restore deleted data - this is a one-way migration."""
    pass
