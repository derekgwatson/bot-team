#!/usr/bin/env python3
"""
Integration test script for Banji.

Tests the full workflow with real browser automation.
Requires Banji to be running on localhost:8014.

Usage:
    python tools/test_banji_integration.py --org designer_drapes --quote 12345
"""
import sys
import argparse
import requests
import time
from pathlib import Path


class Colors:
    """Terminal colors for output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_success(msg):
    print(f"{Colors.GREEN}✓{Colors.END} {msg}")


def print_error(msg):
    print(f"{Colors.RED}✗{Colors.END} {msg}")


def print_warning(msg):
    print(f"{Colors.YELLOW}⚠{Colors.END} {msg}")


def print_info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.END} {msg}")


def print_header(msg):
    print(f"\n{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{msg}{Colors.END}")
    print(f"{Colors.BOLD}{'='*60}{Colors.END}\n")


class BanjiIntegrationTest:
    """Integration tester for Banji."""

    def __init__(self, base_url="http://localhost:8014", api_key="your-bot-api-key-here"):
        self.base_url = base_url
        self.api_key = api_key
        self.session_id = None
        self.passed = 0
        self.failed = 0

    def _request(self, method, path, **kwargs):
        """Make HTTP request with API key."""
        headers = kwargs.get('headers', {})
        headers['X-API-Key'] = self.api_key
        kwargs['headers'] = headers

        url = f"{self.base_url}{path}"
        response = requests.request(method, url, **kwargs)

        return response

    def test_health(self):
        """Test health endpoint."""
        print_info("Testing health endpoint...")
        try:
            response = requests.get(f"{self.base_url}/health")
            response.raise_for_status()

            data = response.json()
            assert data['status'] == 'healthy', "Health check failed"
            assert 'bot' in data, "Missing bot name"

            print_success(f"Health check passed: {data['bot']} v{data['version']}")
            print_info(f"  Browser mode: {data['browser_mode']}")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Health check failed: {e}")
            self.failed += 1
            return False

    def test_info(self):
        """Test info endpoint."""
        print_info("Testing info endpoint...")
        try:
            response = requests.get(f"{self.base_url}/info")
            response.raise_for_status()

            data = response.json()
            assert 'capabilities' in data, "Missing capabilities"
            assert 'active_sessions' in data, "Missing active sessions"

            print_success("Info endpoint working")
            print_info(f"  Active sessions: {data['active_sessions']}")
            print_info(f"  Session timeout: {data['session_timeout_minutes']} minutes")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Info endpoint failed: {e}")
            self.failed += 1
            return False

    def test_create_session(self, org):
        """Test creating a session."""
        print_info(f"Creating session for org: {org}")
        try:
            response = self._request(
                'POST',
                '/api/sessions/start',
                json={'org': org}
            )
            response.raise_for_status()

            data = response.json()
            self.session_id = data['session_id']

            print_success(f"Session created: {self.session_id}")
            print_info(f"  Organization: {data['org']}")
            print_info(f"  Timeout: {data['timeout_minutes']} minutes")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Session creation failed: {e}")
            if hasattr(e, 'response') and e.response:
                print_error(f"  Response: {e.response.text}")
            self.failed += 1
            return False

    def test_navigate_to_quote(self, quote_id):
        """Test navigating to a quote."""
        if not self.session_id:
            print_warning("Skipping - no active session")
            return False

        print_info(f"Navigating to quote: {quote_id}")
        try:
            response = self._request(
                'POST',
                f'/api/sessions/{self.session_id}/navigate/quote',
                json={'quote_id': quote_id}
            )
            response.raise_for_status()

            data = response.json()
            print_success(f"Navigated to quote {quote_id}")
            print_info(f"  Order PK ID: {data['order_pk_id']}")
            print_info(f"  URL: {data['current_url']}")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Navigation failed: {e}")
            if hasattr(e, 'response') and e.response:
                try:
                    error_data = e.response.json()
                    print_error(f"  Error: {error_data.get('error', e.response.text)}")
                except:
                    print_error(f"  Response: {e.response.text}")
            self.failed += 1
            return False

    def test_get_total_price(self):
        """Test getting quote total price."""
        if not self.session_id:
            print_warning("Skipping - no active session")
            return False

        print_info("Getting quote total price...")
        try:
            response = self._request(
                'GET',
                f'/api/sessions/{self.session_id}/quote/total'
            )
            response.raise_for_status()

            data = response.json()
            print_success(f"Got total price: ${data['total_price']:.2f}")
            if data.get('quote_id'):
                print_info(f"  Quote ID: {data['quote_id']}")
            self.passed += 1
            return data['total_price']

        except Exception as e:
            print_error(f"Get total price failed: {e}")
            if hasattr(e, 'response') and e.response:
                print_error(f"  Response: {e.response.text}")
            self.failed += 1
            return None

    def test_open_bulk_edit(self):
        """Test opening bulk edit."""
        if not self.session_id:
            print_warning("Skipping - no active session")
            return False

        print_info("Opening bulk edit mode...")
        try:
            response = self._request(
                'POST',
                f'/api/sessions/{self.session_id}/bulk-edit/open',
                json={}  # Empty body but sets Content-Type header
            )
            response.raise_for_status()

            data = response.json()
            print_success("Bulk edit opened")
            print_info(f"  Status: {data['status']}")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Open bulk edit failed: {e}")
            if hasattr(e, 'response') and e.response:
                print_error(f"  Response: {e.response.text}")
            self.failed += 1
            return False

    def test_save_bulk_edit(self):
        """Test saving bulk edit (triggers price recalc)."""
        if not self.session_id:
            print_warning("Skipping - no active session")
            return False

        print_info("Saving bulk edit (triggering price recalc)...")
        try:
            response = self._request(
                'POST',
                f'/api/sessions/{self.session_id}/bulk-edit/save',
                json={}  # Empty body but sets Content-Type header
            )
            response.raise_for_status()

            data = response.json()
            print_success("Bulk edit saved")
            print_info(f"  Status: {data['status']}")
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Save bulk edit failed: {e}")
            if hasattr(e, 'response') and e.response:
                print_error(f"  Response: {e.response.text}")
            self.failed += 1
            return False

    def test_close_session(self):
        """Test closing a session."""
        if not self.session_id:
            print_warning("No session to close")
            return False

        print_info(f"Closing session: {self.session_id}")
        try:
            response = self._request(
                'DELETE',
                f'/api/sessions/{self.session_id}'
            )
            response.raise_for_status()

            print_success("Session closed")
            self.session_id = None
            self.passed += 1
            return True

        except Exception as e:
            print_error(f"Close session failed: {e}")
            self.failed += 1
            return False

    def test_full_workflow(self, org, quote_id):
        """Test complete pricing refresh workflow."""
        print_header("Full Pricing Refresh Workflow Test")

        # Create session
        if not self.test_create_session(org):
            return False

        try:
            # Navigate to quote
            if not self.test_navigate_to_quote(quote_id):
                return False

            # Get price before
            price_before = self.test_get_total_price()
            if price_before is None:
                return False

            # Open bulk edit
            if not self.test_open_bulk_edit():
                return False

            # Save (trigger recalc)
            if not self.test_save_bulk_edit():
                return False

            # Navigate back to quote to see new price
            print_info("Navigating back to quote summary...")
            if not self.test_navigate_to_quote(quote_id):
                return False

            # Get price after
            price_after = self.test_get_total_price()
            if price_after is None:
                return False

            # Compare prices
            price_diff = price_after - price_before
            if abs(price_diff) > 0.01:
                print_warning(f"PRICE CHANGED! Difference: ${price_diff:.2f}")
                print_info(f"  Before: ${price_before:.2f}")
                print_info(f"  After: ${price_after:.2f}")
            else:
                print_success("Price unchanged")

            return True

        finally:
            # Always close session
            self.test_close_session()

    def run_basic_tests(self):
        """Run basic infrastructure tests."""
        print_header("Basic Infrastructure Tests")

        self.test_health()
        self.test_info()

    def print_summary(self):
        """Print test summary."""
        print_header("Test Summary")

        total = self.passed + self.failed
        print(f"Total tests: {total}")
        print_success(f"Passed: {self.passed}")

        if self.failed > 0:
            print_error(f"Failed: {self.failed}")
            return False
        else:
            print_success("All tests passed!")
            return True


def main():
    parser = argparse.ArgumentParser(description='Test Banji integration')
    parser.add_argument('--base-url', default='http://localhost:8014',
                        help='Banji base URL')
    parser.add_argument('--api-key', default='your-bot-api-key-here',
                        help='API key for authentication')
    parser.add_argument('--org', help='Organization name (e.g., designer_drapes)')
    parser.add_argument('--quote', help='Quote ID to test with')
    parser.add_argument('--basic-only', action='store_true',
                        help='Run only basic tests (no browser automation)')

    args = parser.parse_args()

    tester = BanjiIntegrationTest(base_url=args.base_url, api_key=args.api_key)

    # Always run basic tests
    tester.run_basic_tests()

    # Run full workflow if org and quote provided
    if not args.basic_only:
        if args.org and args.quote:
            tester.test_full_workflow(args.org, args.quote)
        else:
            print_warning("\nSkipping workflow tests - provide --org and --quote to test full workflow")
            print_info("Example: python tools/test_banji_integration.py --org designer_drapes --quote 12345")

    # Summary
    success = tester.print_summary()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
