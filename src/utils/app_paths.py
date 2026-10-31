from __future__ import annotations

import os
import sys
from pathlib import Path


APP_DIR_NAME = "SleepSense"
VISIBLE_DATA_DIR_NAME = "SleepSense User Data"


def get_app_root() -> Path:
    """Return the base directory that contains bundled app resources."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def _first_existing_env_dir(*env_vars: str) -> Path | None:
    for env_var in env_vars:
        value = os.environ.get(env_var)
        if value:
            return Path(value)
    return None


def get_data_root() -> Path:
    """
    Return the persistent writable root for Sleep Sense data.

    Prefer ProgramData so reinstalling or replacing the EXE does not remove
    patient data. Fall back to LocalAppData if ProgramData is unavailable.
    """
    candidates = [
        _first_existing_env_dir("PROGRAMDATA"),
        _first_existing_env_dir("LOCALAPPDATA", "APPDATA"),
    ]
    for base_dir in candidates:
        if base_dir is None:
            continue
        candidate = base_dir / APP_DIR_NAME
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except OSError:
            continue

    fallback = get_app_root() / "data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_data_path(*parts: str) -> Path:
    """Build an absolute path inside the persistent writable data root."""
    path = get_data_root().joinpath(*parts)
    if parts:
        path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_user_visible_data_root() -> Path:
    """
    Return a user-visible folder for mirrored raw data and database backups.

    When running as an EXE, prefer a folder next to the installed app so the
    visible mirror travels with the deployment. Fall back to Documents/Home if
    that location is not writable.
    """
    candidates = [
        Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else None,
        get_app_root() if not getattr(sys, "frozen", False) else None,
        Path.home() / "Documents",
        Path.home(),
    ]
    for base_dir in candidates:
        if base_dir is None:
            continue
        try:
            base_dir.mkdir(parents=True, exist_ok=True)
            visible_root = base_dir / VISIBLE_DATA_DIR_NAME
            visible_root.mkdir(parents=True, exist_ok=True)
            return visible_root
        except OSError:
            continue

    fallback = get_app_root() / "visible_data"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def get_resource_path(*parts: str) -> str:
    """Build an absolute path to a bundled resource."""
    return str(get_app_root().joinpath(*parts))
