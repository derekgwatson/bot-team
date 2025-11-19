import yaml
from pathlib import Path

SHARED_CONFIG_DIR = Path(__file__).parent


def load_shared_yaml(name: str) -> dict:
    """
    Load a YAML file from shared/config by base name.

    Example:
        org = load_shared_yaml("organization")
    """
    path = SHARED_CONFIG_DIR / f"{name}.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}
