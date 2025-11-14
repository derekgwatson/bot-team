#!/usr/bin/env python3
"""
Diagnostic tool to test Google Sheets credentials for Peter
Run this on the prod server to debug authentication issues

Usage:
    cd /var/www/bot-team/peter
    ./.venv/bin/python test_credentials.py
"""

import os
import sys
import json
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

def main():
    print("=" * 60)
    print("Peter Credentials Diagnostic Tool")
    print("=" * 60)
    print()

    # Load environment variables
    load_dotenv()

    # Check credentials file
    creds_file = "credentials.json"
    print(f"1. Checking credentials file: {creds_file}")

    if not os.path.exists(creds_file):
        print(f"   ❌ FAIL: File not found at {os.path.abspath(creds_file)}")
        print()
        print("   DIAGNOSIS: Missing credentials file")
        print()
        print("   Peter needs a Google Cloud service account with Sheets API access.")
        print("   The credentials.json file should be in /var/www/bot-team/peter/")
        print()
        print("   Steps to fix:")
        print("   1. Create or obtain the service account JSON key")
        print("   2. Copy it to /var/www/bot-team/peter/credentials.json")
        print("   3. Ensure file is readable by www-data user")
        print("   4. Grant service account access to your Google Sheet")
        return 1

    print(f"   ✓ File exists at {os.path.abspath(creds_file)}")

    # Read and validate credentials file
    print()
    print("2. Reading credentials file...")
    try:
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)

        service_account_email = creds_data.get('client_email', 'MISSING')
        project_id = creds_data.get('project_id', 'MISSING')

        print(f"   ✓ Valid JSON format")
        print(f"   Service account: {service_account_email}")
        print(f"   Project ID: {project_id}")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return 1

    # Check configuration
    print()
    print("3. Checking configuration...")

    from config import config

    spreadsheet_id = config.spreadsheet_id
    sheet_name = config.sheet_name

    if not spreadsheet_id:
        print(f"   ❌ FAIL: spreadsheet_id not configured in config.yaml")
        return 1

    print(f"   ✓ Spreadsheet ID: {spreadsheet_id}")
    print(f"   ✓ Sheet name: {sheet_name}")

    # Test creating credentials
    print()
    print("4. Testing service account credentials...")
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets']

        credentials = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=scopes
        )
        print(f"   ✓ Service account credentials loaded successfully")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return 1

    # Test actual API call
    print()
    print("5. Testing actual API call to Google Sheets...")
    try:
        service = build('sheets', 'v4', credentials=credentials)

        # Try to read from the spreadsheet
        range_name = f"{sheet_name}!A1:E10"
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()

        rows = result.get('values', [])
        print(f"   ✓ SUCCESS! API call worked")
        print(f"   Retrieved {len(rows)} row(s) from '{sheet_name}'")

        if rows:
            print(f"   First row: {rows[0]}")

    except HttpError as e:
        print(f"   ❌ FAIL: HTTP {e.resp.status}")

        if e.resp.status == 403:
            print()
            print("   DIAGNOSIS: Permission denied")
            print()
            print("   The service account doesn't have access to the spreadsheet.")
            print()
            print("   Steps to fix:")
            print(f"   1. Open the Google Sheet (ID: {spreadsheet_id})")
            print(f"   2. Click 'Share' button")
            print(f"   3. Add '{service_account_email}' with Viewer or Editor access")
            print(f"   4. Make sure Sheets API is enabled in Google Cloud Console")

        elif e.resp.status == 404:
            print()
            print("   DIAGNOSIS: Spreadsheet not found")
            print()
            print(f"   The spreadsheet ID '{spreadsheet_id}' doesn't exist")
            print(f"   or the service account doesn't have access to it.")
            print()
            print("   Steps to fix:")
            print("   1. Verify the spreadsheet ID in config.yaml is correct")
            print(f"   2. Share the spreadsheet with '{service_account_email}'")

        return 1

    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # All tests passed!
    print()
    print("=" * 60)
    print("✓ ALL TESTS PASSED - Credentials are working correctly!")
    print("=" * 60)
    return 0

if __name__ == '__main__':
    sys.exit(main())
