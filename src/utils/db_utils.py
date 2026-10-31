import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


APP_NAME = "SleepSense"

# Try migration only once, not on every get_db_path() call
_LEGACY_MIGRATION_DONE = False


def get_app_data_dir() -> Path:
    """Standard OS user-data folder.

    Why: the DB used to be created in the data/ folder next to the exe. As
    soon as the exe was installed somewhere else, the app stopped showing the
    old data (nothing was deleted, the path simply changed). This folder stays
    fixed on the machine, so whether the exe is on C:, D:, or the Desktop, the
    DB is found in one place.

        Windows : C:/Users/<user>/AppData/Local/SleepSense/data
        macOS   : ~/Library/Application Support/SleepSense/data
        Linux   : ~/.local/share/SleepSense/data
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")

    return Path(base) / APP_NAME / "data"


def _legacy_data_dirs() -> list:
    """Old locations where the DB used to be created (for migration)."""
    candidates = [
        # Development: project_root/data
        Path(__file__).resolve().parents[2] / "data",
        # The buggy phase when db_utils.py was moved into src/utils/
        Path(__file__).resolve().parent / "data",
    ]

    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).resolve()
        candidates.extend([
            exe.parent / "data",
            exe.parent.parent / "data",
            exe.parent.parent.parent / "data",
        ])

    unique = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique


def _repoint_session_files(db_file: Path, new_csv_dir: Path) -> None:
    """Move sessions.file_path entries from the old folder to the new one."""
    if not db_file.exists():
        return

    conn = sqlite3.connect(str(db_file), timeout=10)
    try:
        c = conn.cursor()
        c.execute("PRAGMA table_info(sessions)")
        if not c.fetchall():
            return

        c.execute("SELECT id, file_path FROM sessions")
        updated = 0
        for session_id, file_path in c.fetchall():
            if not file_path:
                continue
            candidate = new_csv_dir / Path(file_path).name
            if candidate.exists() and str(candidate) != file_path:
                c.execute(
                    "UPDATE sessions SET file_path = ? WHERE id = ?",
                    (str(candidate), session_id),
                )
                updated += 1
        conn.commit()
        if updated:
            pass
    except sqlite3.Error as error:
        print(f"[SleepSense] Could not update session paths: {error}")
    finally:
        conn.close()


def _migrate_legacy_data(target_dir: Path) -> bool:
    """Copy the DB to the new folder if it is found in an old location. Old data is not deleted."""
    target_db = target_dir / "sleep_sense.db"

    for legacy_dir in _legacy_data_dirs():
        legacy_db = legacy_dir / "sleep_sense.db"
        if not legacy_db.exists() or legacy_db.resolve() == target_db.resolve():
            continue

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_db, target_db)

            # In WAL mode, the latest writes may live in the -wal file, so copy it too.
            for suffix in ("-wal", "-shm"):
                side_file = Path(str(legacy_db) + suffix)
                if side_file.exists():
                    shutil.copy2(side_file, Path(str(target_db) + suffix))

            legacy_csv = legacy_dir / "raw_csv"
            new_csv_dir = target_dir / "raw_csv"
            if legacy_csv.is_dir():
                shutil.copytree(legacy_csv, new_csv_dir, dirs_exist_ok=True)
                _repoint_session_files(target_db, new_csv_dir)

            pass
            return True
        except Exception as error:
            print(f"[SleepSense] Migration failed ({legacy_dir}): {error}")

    return False


def get_db_path() -> str:
    """Return the sleep_sense.db path, independent of the exe location.

    On first run, old data migrates automatically.
    """
    global _LEGACY_MIGRATION_DONE

    target_dir = get_app_data_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    db_path = target_dir / "sleep_sense.db"

    if not db_path.exists() and not _LEGACY_MIGRATION_DONE:
        _LEGACY_MIGRATION_DONE = True
        _migrate_legacy_data(target_dir)

    return str(db_path)


def init_db():
    """
    Call once at app startup.
    Creates tables if missing and leaves existing ones unchanged.
    """
    conn = sqlite3.connect(get_db_path())
    conn.executescript("""
        PRAGMA journal_mode = WAL;

        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  TEXT NOT NULL,
            saved_at    TEXT NOT NULL,
            file_path   TEXT NOT NULL DEFAULT '',
            patient_db_id INTEGER,
            duration    TEXT NOT NULL DEFAULT '',
            parent_session_id INTEGER
        );
    """)
    _ensure_sessions_columns(conn)
    conn.commit()
    conn.close()


def _ensure_sessions_columns(conn: sqlite3.Connection):
    """Migrate older sessions tables that may not have the latest columns yet."""
    c = conn.cursor()
    c.execute("PRAGMA table_info(sessions)")
    columns = {row[1] for row in c.fetchall()}
    if "file_path" not in columns:
        c.execute("ALTER TABLE sessions ADD COLUMN file_path TEXT NOT NULL DEFAULT ''")
    if "patient_db_id" not in columns:
        c.execute("ALTER TABLE sessions ADD COLUMN patient_db_id INTEGER")
    if "duration" not in columns:
        c.execute("ALTER TABLE sessions ADD COLUMN duration TEXT NOT NULL DEFAULT ''")
    if "parent_session_id" not in columns:
        # Links a Re-analyze -> "New report" save back to the original
        # recording it came from, so the Records table can nest reanalyzed
        # versions under the same patient/recording instead of listing them
        # as unrelated rows. NULL means "this is an original recording".
        c.execute("ALTER TABLE sessions ADD COLUMN parent_session_id INTEGER")


_ensure_sessions_file_path_column = _ensure_sessions_columns


def get_raw_recording_dir() -> str:
    """Folder where uploaded binary recording copies are saved."""
    base = Path(get_db_path()).resolve().parent / "raw_recordings"
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def get_visible_raw_recording_dir() -> str:
    """Return the folder shown by the UI for saved recording copies."""
    return get_raw_recording_dir()


def save_raw_recording_session(
    patient_id: str,
    source_recording_path: str,
    patient_db_id: int = None,
    duration: str = "",
    parent_session_id: int = None,
) -> tuple:
    """
    Parameters:
        patient_id : "PATIENT001"
        source_recording_path : uploaded binary SD recording
        parent_session_id : id of the original session this save belongs to,
            when this call is a Re-analyze -> "New report" save of an
            existing recording. Leave None for a brand new recording.
    Returns:
        (session_id: int, saved_at: str, copied_recording_path: str)
    """

    patient_id = (patient_id or "").strip()
    if not patient_db_id and patient_id in ("", "--------"):
        raise ValueError("Patient ID has not been selected.")
    if not patient_id:
        patient_id = str(patient_db_id)

    source = Path(source_recording_path or "")
    if not source.exists():
        raise ValueError("Source recording file not found.")

    saved_at = datetime.now().isoformat(timespec="seconds")

    safe_patient = "".join(ch if ch.isalnum() or ch in ("_", "-") else "_" for ch in patient_id)
    safe_ts = saved_at.replace(":", "-")
    dest_dir = Path(get_raw_recording_dir())
    dest_name = f"{safe_patient}_{safe_ts}_{source.name}"
    dest_path = dest_dir / dest_name

    shutil.copy2(source, dest_path)

    conn = sqlite3.connect(get_db_path(), timeout=10)
    try:
        c = conn.cursor()
        _ensure_sessions_columns(conn)

        c.execute(
            "INSERT INTO sessions (patient_id, saved_at, file_path, patient_db_id, duration, parent_session_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (patient_id, saved_at, str(dest_path), patient_db_id, duration or "", parent_session_id)
        )
        session_id = c.lastrowid
        conn.commit()
        return session_id, saved_at, str(dest_path)

    except sqlite3.OperationalError as e:
        conn.rollback()
        if dest_path.exists():
            dest_path.unlink()
        raise RuntimeError(f"Database error: {e}")
    except Exception:
        conn.rollback()
        if dest_path.exists():
            dest_path.unlink()
        raise
    finally:
        conn.close()


def list_sessions(patient_id: str = None, patient_db_id: int = None) -> list:
    """Return all sessions for display in the sidebar."""
    conn = sqlite3.connect(get_db_path(), timeout=10)
    c = conn.cursor()
    _ensure_sessions_columns(conn)
    conn.commit()
    if patient_db_id is not None:
        if patient_id:
            c.execute(
                "SELECT id, patient_id, saved_at, file_path, patient_db_id, duration, parent_session_id FROM sessions "
                "WHERE patient_db_id = ? OR (patient_db_id IS NULL AND patient_id = ?) "
                "ORDER BY saved_at DESC",
                (patient_db_id, patient_id)
            )
        else:
            c.execute(
                "SELECT id, patient_id, saved_at, file_path, patient_db_id, duration, parent_session_id FROM sessions "
                "WHERE patient_db_id = ? ORDER BY saved_at DESC",
                (patient_db_id,)
            )
    elif patient_id:
        c.execute(
            "SELECT id, patient_id, saved_at, file_path, patient_db_id, duration, parent_session_id FROM sessions "
            "WHERE patient_id = ? ORDER BY saved_at DESC",
            (patient_id,)
        )
    else:
        c.execute(
            "SELECT id, patient_id, saved_at, file_path, patient_db_id, duration, parent_session_id FROM sessions ORDER BY saved_at DESC"
        )
    rows = [{"id": r[0], "patient_id": r[1], "saved_at": r[2], "file_path": r[3], "patient_db_id": r[4], "duration": r[5] or "", "parent_session_id": r[6]}
            for r in c.fetchall()]
    conn.close()
    return rows
