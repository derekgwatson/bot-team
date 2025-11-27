"""
Buz organization configuration.

Provides centralized org configuration for Buz-interacting bots.
Each org has authentication stored in a Playwright storage state file.
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BuzOrgs:
    """
    Manages Buz organization configurations.

    Orgs are loaded from BUZ_ORGS environment variable and storage state
    files are expected in {bot_dir}/.secrets/buz_storage_state_{org}.json

    The storage state files are created using the buz_auth_bootstrap.py tool.
    """

    # Default org display names (can be extended)
    ORG_DISPLAY_NAMES = {
        'canberra': 'Canberra',
        'tweed': 'Tweed',
        'dd': 'Designer Drapes',
        'bay': 'Batemans Bay',
        'shoalhaven': 'Shoalhaven',
        'wagga': 'Wagga Wagga',
    }

    # Orgs that have customers (not just employees)
    ORGS_WITH_CUSTOMERS = {'canberra', 'dd'}

    @classmethod
    def load_orgs(
        cls,
        secrets_dir: Path,
        env_var: str = 'BUZ_ORGS'
    ) -> Tuple[Dict[str, dict], Dict[str, str]]:
        """
        Load Buz organization configurations from environment.

        Args:
            secrets_dir: Directory containing storage state files
            env_var: Environment variable name containing org list

        Returns:
            Tuple of (configured_orgs, missing_auth_orgs)
            - configured_orgs: dict of org_name -> {name, display_name, storage_state_path, has_customers}
            - missing_auth_orgs: dict of org_name -> expected_path
        """
        orgs_env = os.environ.get(env_var, '').strip()
        if not orgs_env:
            return {}, {}

        orgs = {}
        missing_auth = {}
        org_names = [name.strip() for name in orgs_env.split(',') if name.strip()]

        for org_name in org_names:
            storage_state_file = secrets_dir / f'buz_storage_state_{org_name}.json'

            if not storage_state_file.exists():
                missing_auth[org_name] = str(storage_state_file.resolve())
            else:
                orgs[org_name] = {
                    'name': org_name,
                    'display_name': cls.ORG_DISPLAY_NAMES.get(org_name, org_name.title()),
                    'storage_state_path': str(storage_state_file.resolve()),
                    'has_customers': org_name in cls.ORGS_WITH_CUSTOMERS,
                }

        return orgs, missing_auth

    @classmethod
    def get_display_name(cls, org_name: str) -> str:
        """Get display name for an org."""
        return cls.ORG_DISPLAY_NAMES.get(org_name, org_name.title())

    @classmethod
    def has_customers(cls, org_name: str) -> bool:
        """Check if an org has customer users (not just employees)."""
        return org_name in cls.ORGS_WITH_CUSTOMERS

    @classmethod
    def print_setup_instructions(cls, missing_auth: Dict[str, str]) -> None:
        """Print setup instructions for missing auth files."""
        if not missing_auth:
            return

        print("\n Warning: Some organizations are missing authentication")
        for org_name, expected_path in missing_auth.items():
            print(f"  - {org_name}: {expected_path}")
        print("\n Run this to set up authentication:")
        for org_name in missing_auth.keys():
            print(f"    python tools/buz_auth_bootstrap.py {org_name}")
        print()
