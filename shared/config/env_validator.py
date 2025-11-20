"""
Environment Variable Validator

Validates that all required environment variables are present before bot startup.
Reads .env.example files to determine what's required and provides clear error messages.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import re


class EnvValidationError(Exception):
    """Raised when environment validation fails"""
    pass


class EnvValidator:
    """Validates environment variables against .env.example files"""

    def __init__(self, bot_dir: Path = None):
        """
        Initialize the validator

        Args:
            bot_dir: Path to the bot's directory (e.g., /path/to/bot-team/zac)
                    If None, only validates shared .env
        """
        self.bot_dir = bot_dir
        self.root_dir = Path(__file__).resolve().parents[2]  # bot-team/
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def parse_env_example(self, env_example_path: Path, bot_name: str = None) -> Dict[str, dict]:
        """
        Parse a .env.example file and extract variable definitions

        Args:
            env_example_path: Path to the .env.example file
            bot_name: Name of the bot (used to filter shared variables)

        Returns:
            Dict mapping variable names to metadata:
            {
                'VAR_NAME': {
                    'required': bool,
                    'description': str,
                    'example': str,
                    'used_by': List[str]  # List of bots that use this variable
                }
            }
        """
        if not env_example_path.exists():
            return {}

        variables = {}
        current_comments = []
        current_section_bots = []  # Track which bots the current section applies to

        with open(env_example_path, 'r') as f:
            for line in f:
                line = line.rstrip()

                # Skip empty lines
                if not line:
                    current_comments = []
                    continue

                # Collect comments for context
                if line.startswith('#'):
                    comment_text = line.lstrip('#').strip()
                    current_comments.append(comment_text)

                    # Check for section headers with bot names like "── Google Workspace API (Fred, Iris) ─────"
                    section_match = re.search(r'──\s*([^(]+)\s*\(([^)]+)\)', comment_text)
                    if section_match:
                        bots_text = section_match.group(2)
                        current_section_bots = [
                            bot.strip().lower()
                            for bot in re.split(r'[,\s]+', bots_text)
                            if bot.strip() and bot.strip().lower() not in ['api', 'for', 'with']
                        ]

                    # Also check for "Used by:" pattern
                    used_by_match = re.search(r'[Uu]sed by:([^─\n]+)', comment_text)
                    if used_by_match:
                        bots_text = used_by_match.group(1)
                        current_section_bots = [
                            bot.strip().lower()
                            for bot in re.split(r'[,\s]+', bots_text)
                            if bot.strip()
                        ]

                    continue

                # Parse variable definitions
                match = re.match(r'^([A-Z_][A-Z0-9_]*)=(.*)$', line)
                if match:
                    var_name = match.group(1)
                    example_value = match.group(2)

                    description = ' '.join(current_comments)

                    # Determine if required (not optional)
                    is_optional = any(
                        keyword in description.lower()
                        for keyword in ['optional', 'only required if', 'note:', 'example for']
                    )

                    # Use the section's bot list or look for inline "Used by:"
                    used_by = current_section_bots.copy() if current_section_bots else []

                    # If this is a shared .env and bot_name is specified
                    # only require this variable if the bot is in the used_by list
                    # or if there's no used_by restriction
                    is_required_for_bot = not is_optional
                    if bot_name and used_by:
                        is_required_for_bot = bot_name.lower() in used_by

                    variables[var_name] = {
                        'required': is_required_for_bot,
                        'description': description,
                        'example': example_value,
                        'used_by': used_by
                    }

                    current_comments = []

        return variables

    def check_variable(self, var_name: str, metadata: dict, source: str) -> bool:
        """
        Check if a variable is set in the environment

        Args:
            var_name: Name of the environment variable
            metadata: Variable metadata from parse_env_example
            source: Description of where this variable is defined (for error messages)

        Returns:
            True if valid, False otherwise
        """
        value = os.environ.get(var_name)

        # Check if variable is set
        if value is None or value == '':
            if metadata['required']:
                self.errors.append(
                    f"❌ Missing required variable: {var_name}\n"
                    f"   Source: {source}\n"
                    f"   Description: {metadata['description']}\n"
                    f"   Example: {var_name}={metadata['example']}"
                )
                return False
            return True

        # Check for placeholder values (common mistakes)
        placeholder_patterns = [
            'your-',
            'change-in-production',
            'example.com',
            '/path/to/',
            'yourcompany',
            'yourdomain',
        ]

        if metadata['required'] and any(pattern in value.lower() for pattern in placeholder_patterns):
            self.warnings.append(
                f"⚠️  Variable appears to have placeholder value: {var_name}\n"
                f"   Current value: {value}\n"
                f"   Description: {metadata['description']}"
            )

        return True

    def validate_shared_env(self) -> Set[str]:
        """
        Validate the shared .env file at the root

        Returns:
            Set of variable names that were validated
        """
        shared_env_example = self.root_dir / '.env.example'
        bot_name = self.bot_dir.name if self.bot_dir else None
        variables = self.parse_env_example(shared_env_example, bot_name=bot_name)

        validated_vars = set()
        for var_name, metadata in variables.items():
            # Only check variables that are required for this bot
            if metadata['required']:
                self.check_variable(var_name, metadata, "shared .env (bot-team/.env)")
            validated_vars.add(var_name)

        return validated_vars

    def validate_bot_env(self) -> Set[str]:
        """
        Validate the bot-specific .env file

        Returns:
            Set of variable names that were validated
        """
        if not self.bot_dir:
            return set()

        bot_env_example = self.bot_dir / '.env.example'
        variables = self.parse_env_example(bot_env_example)

        validated_vars = set()
        bot_name = self.bot_dir.name

        for var_name, metadata in variables.items():
            if metadata['required']:
                self.check_variable(var_name, metadata, f"{bot_name}/.env")
            validated_vars.add(var_name)

        return validated_vars

    def validate(self, strict: bool = True) -> bool:
        """
        Run full validation

        Args:
            strict: If True, warnings are treated as errors

        Returns:
            True if validation passes, False otherwise

        Raises:
            EnvValidationError if validation fails
        """
        self.errors = []
        self.warnings = []

        # Validate shared environment
        self.validate_shared_env()

        # Validate bot-specific environment
        if self.bot_dir:
            self.validate_bot_env()

        # Report results
        has_errors = len(self.errors) > 0
        has_warnings = len(self.warnings) > 0

        if has_errors or (strict and has_warnings):
            error_msg = self._format_error_message()
            raise EnvValidationError(error_msg)

        if has_warnings:
            print("\n" + "="*60)
            print("⚠️  Environment Variable Warnings")
            print("="*60)
            for warning in self.warnings:
                print(f"\n{warning}")
            print("\n" + "="*60 + "\n")

        return True

    def _format_error_message(self) -> str:
        """Format a comprehensive error message"""
        lines = [
            "",
            "="*60,
            "❌ Environment Variable Validation Failed",
            "="*60,
            "",
        ]

        if self.errors:
            lines.append("ERRORS:")
            lines.append("")
            for error in self.errors:
                lines.append(error)
                lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            lines.append("")
            for warning in self.warnings:
                lines.append(warning)
                lines.append("")

        lines.extend([
            "="*60,
            "",
            "How to fix:",
            "1. Check your .env files exist:",
        ])

        if self.bot_dir:
            lines.append(f"   - {self.bot_dir}/.env")
        lines.append(f"   - {self.root_dir}/.env")

        lines.extend([
            "",
            "2. Copy from .env.example if needed:",
        ])

        if self.bot_dir:
            lines.append(f"   cp {self.bot_dir}/.env.example {self.bot_dir}/.env")
        lines.append(f"   cp {self.root_dir}/.env.example {self.root_dir}/.env")

        lines.extend([
            "",
            "3. Fill in all required values with your actual credentials",
            "",
            "="*60,
            ""
        ])

        return "\n".join(lines)


def validate_env(bot_name: str = None, strict: bool = True) -> bool:
    """
    Convenience function to validate environment variables

    Args:
        bot_name: Name of the bot (e.g., 'zac', 'sally'). If None, only validates shared env
        strict: If True, warnings are treated as errors

    Returns:
        True if validation passes

    Raises:
        EnvValidationError if validation fails
    """
    root_dir = Path(__file__).resolve().parents[2]
    bot_dir = root_dir / bot_name if bot_name else None

    validator = EnvValidator(bot_dir)
    return validator.validate(strict=strict)


if __name__ == '__main__':
    """Allow running validator standalone for testing"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate environment variables')
    parser.add_argument('bot_name', nargs='?', help='Bot name to validate (e.g., zac, sally)')
    parser.add_argument('--strict', action='store_true', help='Treat warnings as errors')

    args = parser.parse_args()

    try:
        validate_env(args.bot_name, strict=args.strict)
        print("✅ Environment validation passed!")
        sys.exit(0)
    except EnvValidationError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
