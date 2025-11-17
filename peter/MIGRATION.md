# Peter Migration Guide

## Overview

Peter has been upgraded from a simple phone directory manager to the **central HR database** for the organization. This guide explains the migration from Google Sheets to SQLite.

## What Changed?

### Before
- Peter synced with a Google Sheet phone list
- Limited to basic contact info (name, phone, email, extension)
- Read-only view of organizational data

### After
- Peter maintains a **SQLite database** as the single source of truth
- Tracks comprehensive staff information:
  - Basic contact details
  - System access flags (Zendesk, Buz, Google, Wiki, VOIP)
  - Display preferences (phone list visibility, all-staff group membership)
  - Personal email addresses
  - Employment status
- Provides API for other bots (Quinn, Pam)
- No longer depends on Google Sheets

## Migration Steps

### 1. Run the Migration Script

The migration script reads the existing Google Sheets phone list and populates the new SQLite database:

```bash
cd peter
python3 database/migrate_from_sheets.py
```

This will:
- Read all contacts from the Google Sheet
- Create staff records in the new database
- Set sensible defaults for access flags
- Preserve all contact information

### 2. Review and Update Access Flags

After migration, review each staff member's access flags:

- `zendesk_access`: Does this person have Zendesk access?
- `buz_access`: Does this person have Buz access?
- `google_access`: Does this person have Google Workspace access?
- `wiki_access`: Does this person have Wiki access?
- `voip_access`: Does this person have VOIP phone access?

You can update these through Peter's admin interface (coming soon) or via API.

### 3. Add Personal Email Addresses

For staff without work emails, add their personal email addresses so they can be included in the all-staff Google Group:

```bash
# Via Python script or API
# Example: Update staff member with ID 5
curl -X PUT http://peter:8003/api/contacts/5 \
  -H "Content-Type: application/json" \
  -d '{"personal_email": "john@gmail.com"}'
```

### 4. Configure Display Flags

Set `show_on_phone_list` and `include_in_allstaff` flags appropriately:

- `show_on_phone_list`: Should this person appear on Pam's public phone directory?
- `include_in_allstaff`: Should this person be in the all-staff Google Group?

By default, everyone is included in both.

### 5. Phase Out Google Sheets

Once you've verified the migration and Peter is working correctly:

1. Make the Google Sheet read-only (or delete it)
2. Update onboarding/offboarding processes to use Peter directly
3. Consider building a web admin UI for Peter

## New API Endpoints

### Staff Management

```bash
# Get all staff (includes those not on phone list)
GET /api/staff?status=active

# Get specific staff member
GET /api/staff/<id>

# Get all-staff group members (for Quinn)
GET /api/staff/allstaff-members
```

### Backward Compatible Endpoints

These endpoints maintain the old format for Pam:

```bash
# Get phone list contacts
GET /api/contacts

# Search contacts
GET /api/contacts/search?q=query

# Add/update/delete contacts
POST /api/contacts
PUT /api/contacts/<id>
DELETE /api/contacts/<id>
```

## Database Schema

The new `staff` table includes:

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Full name |
| position | TEXT | Job title |
| section | TEXT | Department/section |
| extension | TEXT | Phone extension |
| phone_fixed | TEXT | Fixed line phone |
| phone_mobile | TEXT | Mobile phone |
| work_email | TEXT | Work email address |
| personal_email | TEXT | Personal email address |
| zendesk_access | BOOLEAN | Has Zendesk access |
| buz_access | BOOLEAN | Has Buz access |
| google_access | BOOLEAN | Has Google access |
| wiki_access | BOOLEAN | Has Wiki access |
| voip_access | BOOLEAN | Has VOIP access |
| show_on_phone_list | BOOLEAN | Show on phone directory |
| include_in_allstaff | BOOLEAN | Include in all-staff group |
| status | TEXT | active/inactive/onboarding/offboarding |
| created_date | TIMESTAMP | When created |
| modified_date | TIMESTAMP | Last modified |
| created_by | TEXT | Who created |
| modified_by | TEXT | Who last modified |
| notes | TEXT | Additional notes |

## Quinn Integration

Quinn has been simplified to just sync the all-staff Google Group. He now:

1. Polls Peter's `/api/staff/allstaff-members` endpoint
2. Compares with current Google Group membership
3. Adds/removes members to keep in sync

Quinn no longer maintains his own database of external staff.

## Pam Integration

Pam continues to work without changes. She still calls Peter's `/api/contacts` endpoint, which now returns data from the SQLite database instead of Google Sheets, filtered to only show staff with `show_on_phone_list=true`.

## Troubleshooting

### Migration script fails

- Ensure Google Sheets credentials are valid
- Check that `config.yaml` has the correct spreadsheet ID
- Verify the sheet name is correct

### Database locked errors

- Only one process should access the database at a time
- Restart Peter if the database gets locked

### Missing staff members

- Check the `status` field - inactive staff won't show by default
- Verify `show_on_phone_list` flag for phone directory visibility
- Check `include_in_allstaff` flag for Google Group inclusion

## Next Steps

Consider building:

1. **Web admin UI** for Peter to manage staff records
2. **Integration with onboarding/offboarding** workflows
3. **API webhooks** to notify other bots when staff data changes
4. **Audit logging** for compliance and tracking changes
