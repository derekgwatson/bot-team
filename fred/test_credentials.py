#!/usr/bin/env python3
"""
Diagnostic tool to test Google Workspace credentials
Run this on the prod server to debug authentication issues

Usage:
    cd /var/www/bot-team/fred
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
    print("Fred Credentials Diagnostic Tool")
    print("=" * 60)
    print()

    # Load environment variables
    load_dotenv()

    # Check credentials file
    creds_file = "credentials.json"
    print(f"1. Checking credentials file: {creds_file}")

    if not os.path.exists(creds_file):
        print(f"   ❌ FAIL: File not found at {os.path.abspath(creds_file)}")
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

    # Check environment variables
    print()
    print("3. Checking environment variables...")

    admin_email = os.environ.get('GOOGLE_WORKSPACE_ADMIN_EMAIL')
    domain = os.environ.get('GOOGLE_WORKSPACE_DOMAIN')

    if not admin_email:
        print(f"   ❌ FAIL: GOOGLE_WORKSPACE_ADMIN_EMAIL not set in .env")
        print(f"   Current .env file: {os.path.abspath('.env')}")
        return 1

    print(f"   ✓ GOOGLE_WORKSPACE_ADMIN_EMAIL = {admin_email}")
    print(f"   ✓ GOOGLE_WORKSPACE_DOMAIN = {domain}")

    # Test creating credentials without delegation
    print()
    print("4. Testing service account credentials (no delegation)...")
    try:
        scopes = [
            'https://www.googleapis.com/auth/admin.directory.user',
            'https://www.googleapis.com/auth/admin.directory.user.readonly'
        ]

        credentials = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=scopes
        )
        print(f"   ✓ Service account credentials loaded successfully")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return 1

    # Test delegation
    print()
    print(f"5. Testing delegation to admin user: {admin_email}")
    try:
        delegated_credentials = credentials.with_subject(admin_email)
        print(f"   ✓ Delegation configured (not yet tested)")
    except Exception as e:
        print(f"   ❌ FAIL: {e}")
        return 1

    # Test actual API call
    print()
    print("6. Testing actual API call to Google Workspace...")
    try:
        service = build('admin', 'directory_v1', credentials=delegated_credentials)

        # Try to list users (just get 1)
        results = service.users().list(
            customer='my_customer',
            maxResults=1,
            orderBy='email'
        ).execute()

        users = results.get('users', [])
        print(f"   ✓ SUCCESS! API call worked")
        print(f"   Retrieved {len(users)} user(s)")

        if users:
            user = users[0]
            print(f"   Sample user: {user.get('primaryEmail')}")

    except HttpError as e:
        print(f"   ❌ FAIL: HTTP {e.resp.status}")
        print(f"   Error: {e.error_details if hasattr(e, 'error_details') else e}")

        if e.resp.status == 403:
            print()
            print("   This is likely a domain-wide delegation issue.")
            print("   Check:")
            print(f"   - Is '{service_account_email}' authorized in Admin Console?")
            print("   - Location: Security → API Controls → Domain-wide delegation")
            print("   - Required scopes:")
            print("     https://www.googleapis.com/auth/admin.directory.user")
            print("     https://www.googleapis.com/auth/admin.directory.user.readonly")

        return 1

    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ FAIL: {error_msg}")

        # Provide specific guidance for common errors
        if 'invalid_grant' in error_msg.lower():
            print()
            print("   DIAGNOSIS: Invalid Grant Error")
            print("   This means the admin email is invalid or doesn't exist.")
            print()
            print("   Possible causes:")
            print(f"   1. '{admin_email}' doesn't exist in your Google Workspace")
            print(f"   2. '{admin_email}' is suspended or deleted")
            print(f"   3. Typo in the email address")
            print()
            print("   Fix:")
            print(f"   - Verify '{admin_email}' exists in Google Admin Console")
            print(f"   - Update GOOGLE_WORKSPACE_ADMIN_EMAIL in .env if incorrect")

        return 1

    # All tests passed!
    print()
    print("=" * 60)
    print("✓ ALL TESTS PASSED - Credentials are working correctly!")
    print("=" * 60)
    return 0

if __name__ == '__main__':
    sys.exit(main())
