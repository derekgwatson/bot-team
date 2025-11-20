"""Update public_facing flags for bots.

Updates the Meet the Team page to show the correct public-facing bots:
- Oscar (onboarding) - set to public
- Olive (offboarding) - set to public
- Rita (staff access) - set to public
- Pam (phone directory) - keep public
- Peter (staff directory admin) - set to NOT public (regular staff don't need access)
- Quinn (external staff backend) - set to NOT public (purely backend now)
"""


def up(conn):
    """Update public_facing flags."""
    cursor = conn.cursor()

    # Set public-facing bots (staff-facing)
    public_bots = ['pam', 'oscar', 'olive', 'rita']
    for bot_name in public_bots:
        cursor.execute('''
            UPDATE bots
            SET public_facing = 1
            WHERE name = ?
        ''', (bot_name,))

    # Set non-public bots (backend/admin only)
    non_public_bots = ['peter', 'quinn']
    for bot_name in non_public_bots:
        cursor.execute('''
            UPDATE bots
            SET public_facing = 0
            WHERE name = ?
        ''', (bot_name,))

    conn.commit()


def down(conn):
    """Revert to previous public_facing flags."""
    cursor = conn.cursor()

    # Revert to original state (pam, peter, quinn public)
    cursor.execute("UPDATE bots SET public_facing = 1 WHERE name IN ('pam', 'peter', 'quinn')")
    cursor.execute("UPDATE bots SET public_facing = 0 WHERE name IN ('oscar', 'olive', 'rita')")

    conn.commit()
