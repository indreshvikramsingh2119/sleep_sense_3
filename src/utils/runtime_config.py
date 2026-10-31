"""
Runtime configuration paths for generated artifacts.
"""

import os
from pathlib import Path

from .db_utils import get_app_data_dir


def _default_paths() -> dict[str, Path]:
    """Return writable locations that survive app upgrades and reinstalls."""
    data_root = get_app_data_dir()
    return {
        "analysis_json_dir": data_root / "analysis_json",
        "debug_reports_dir": data_root / "debug_reports",
        "detector_output_dir": data_root / "detector_output",
    }


def get_configured_path(key: str) -> Path:
    """
    Return a configured directory path.

    Environment overrides are supported via SLEEPSENSE_<KEY>.
    """
    env_key = f"SLEEPSENSE_{key.upper()}"
    configured = os.environ.get(env_key)
    path = Path(configured).expanduser() if configured else _default_paths().get(key)
    if path is None:
        raise KeyError(f"Unknown runtime config key: {key}")
    path.mkdir(parents=True, exist_ok=True)
    return path
