"""
Test runner service for Doc

Executes pytest test suites and captures results.
"""

import logging
import subprocess
import re
import time
from typing import Optional
from pathlib import Path

from config import config
from database.db import db

logger = logging.getLogger(__name__)


class TestRunner:
    """Runs pytest test suites"""

    def __init__(self):
        self.project_root = Path(config.tests_project_root)
        self.default_timeout = config.tests_default_timeout
        self.max_timeout = config.tests_max_timeout

    def run_tests(
        self,
        marker: str = None,
        timeout: int = None,
        verbose: bool = True
    ) -> dict:
        """
        Run pytest tests.

        Args:
            marker: Optional pytest marker (e.g., 'fred', 'integration', 'unit')
            timeout: Optional timeout in seconds (max 600)
            verbose: Whether to run with verbose output

        Returns:
            dict with test results
        """
        # Check if a test run is already in progress
        running = db.get_running_test_run()
        if running:
            return {
                'success': False,
                'error': 'A test run is already in progress',
                'running_since': running['started_at'],
                'marker': running.get('marker')
            }

        # Validate timeout
        if timeout is None:
            timeout = self.default_timeout
        timeout = min(timeout, self.max_timeout)

        # Build pytest command
        cmd = ['python', '-m', 'pytest']

        if marker:
            cmd.extend(['-m', marker])

        if verbose:
            cmd.append('-v')

        # Add test directory
        tests_dir = self.project_root / 'tests'
        cmd.append(str(tests_dir))

        # Start the test run in database
        run_id = db.start_test_run(marker=marker)
        logger.info(f"Starting test run {run_id} with marker={marker}")

        start_time = time.time()

        try:
            # Run pytest
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            duration = time.time() - start_time
            output = result.stdout + '\n' + result.stderr

            # Parse pytest output for stats
            stats = self._parse_pytest_output(output)

            # Determine status
            if result.returncode == 0:
                status = 'passed'
            elif result.returncode == 1:
                status = 'failed'
            else:
                status = 'error'

            # Truncate output if too long (keep last 50KB)
            max_output_len = 50000
            if len(output) > max_output_len:
                output = '... (truncated) ...\n' + output[-max_output_len:]

            # Complete the test run
            db.complete_test_run(
                run_id=run_id,
                status=status,
                total_tests=stats.get('total', 0),
                passed=stats.get('passed', 0),
                failed=stats.get('failed', 0),
                errors=stats.get('errors', 0),
                skipped=stats.get('skipped', 0),
                duration_seconds=duration,
                output=output
            )

            logger.info(f"Test run {run_id} completed: {status}")

            return {
                'success': True,
                'run_id': run_id,
                'status': status,
                'marker': marker,
                'duration_seconds': round(duration, 2),
                'stats': stats,
                'return_code': result.returncode
            }

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time

            db.complete_test_run(
                run_id=run_id,
                status='error',
                duration_seconds=duration,
                error_message=f'Test run timed out after {timeout} seconds'
            )

            logger.error(f"Test run {run_id} timed out after {timeout}s")

            return {
                'success': False,
                'run_id': run_id,
                'status': 'error',
                'marker': marker,
                'duration_seconds': round(duration, 2),
                'error': f'Test run timed out after {timeout} seconds'
            }

        except Exception as e:
            duration = time.time() - start_time

            db.complete_test_run(
                run_id=run_id,
                status='error',
                duration_seconds=duration,
                error_message=str(e)
            )

            logger.exception(f"Test run {run_id} failed with error")

            return {
                'success': False,
                'run_id': run_id,
                'status': 'error',
                'marker': marker,
                'duration_seconds': round(duration, 2),
                'error': str(e)
            }

    def _parse_pytest_output(self, output: str) -> dict:
        """
        Parse pytest output to extract test statistics.

        Looks for lines like:
        - "===== 5 passed in 1.23s ====="
        - "===== 3 passed, 2 failed, 1 skipped in 2.34s ====="
        """
        stats = {
            'total': 0,
            'passed': 0,
            'failed': 0,
            'errors': 0,
            'skipped': 0
        }

        # Look for the summary line at the end
        # Pattern: "====== X passed, Y failed, Z skipped in 1.23s ======"
        summary_pattern = r'=+\s*([\d\w\s,]+)\s+in\s+[\d.]+s\s*=+'
        match = re.search(summary_pattern, output)

        if match:
            summary = match.group(1)

            # Extract counts
            passed_match = re.search(r'(\d+)\s+passed', summary)
            failed_match = re.search(r'(\d+)\s+failed', summary)
            error_match = re.search(r'(\d+)\s+error', summary)
            skipped_match = re.search(r'(\d+)\s+skipped', summary)

            if passed_match:
                stats['passed'] = int(passed_match.group(1))
            if failed_match:
                stats['failed'] = int(failed_match.group(1))
            if error_match:
                stats['errors'] = int(error_match.group(1))
            if skipped_match:
                stats['skipped'] = int(skipped_match.group(1))

            stats['total'] = stats['passed'] + stats['failed'] + stats['errors'] + stats['skipped']

        return stats

    def get_run(self, run_id: int) -> Optional[dict]:
        """Get details of a specific test run"""
        return db.get_test_run(run_id)

    def get_latest_run(self, marker: str = None) -> Optional[dict]:
        """Get the most recent test run"""
        return db.get_latest_test_run(marker)

    def get_run_history(self, limit: int = 20, marker: str = None) -> list:
        """Get test run history"""
        return db.get_test_run_history(limit, marker)

    def is_running(self) -> bool:
        """Check if a test run is currently in progress"""
        return db.get_running_test_run() is not None

    def get_available_markers(self) -> list:
        """
        Get list of available pytest markers.

        Reads from pytest.ini in the project root.
        """
        markers = []
        pytest_ini = self.project_root / 'pytest.ini'

        if pytest_ini.exists():
            try:
                content = pytest_ini.read_text()
                # Look for marker definitions
                in_markers = False
                for line in content.split('\n'):
                    if 'markers' in line and '=' in line:
                        in_markers = True
                        # Check if marker is on same line after =
                        parts = line.split('=', 1)
                        if len(parts) > 1 and parts[1].strip():
                            marker_def = parts[1].strip()
                            if ':' in marker_def:
                                marker_name = marker_def.split(':')[0].strip()
                                markers.append(marker_name)
                        continue

                    if in_markers:
                        line = line.strip()
                        if not line or (not line.startswith(' ') and ':' not in line):
                            in_markers = False
                            continue
                        if ':' in line:
                            marker_name = line.split(':')[0].strip()
                            markers.append(marker_name)

            except Exception as e:
                logger.warning(f"Could not read pytest.ini: {e}")

        return markers


# Singleton instance
test_runner = TestRunner()
