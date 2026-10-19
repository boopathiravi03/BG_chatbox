"""
backend/app/paths.py
Centralized, safe path management for BG AI.
Ensures user data, SQLite databases, logs, and uploads are stored in
Windows %APPDATA%/BG_AI when running packaged or in desktop mode,
preventing readonly permissions errors when installed in Program Files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Returns True if running inside a PyInstaller packaged executable."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_app_data_dir() -> Path:
    """
    Returns the persistent application data directory.
    Priority:
    1. BGAI_DATA_DIR environment variable
    2. %APPDATA%/BG_AI on Windows (in packaged desktop mode or BGAI_DESKTOP_MODE=1)
    3. Project root in local web development mode
    """
    env_dir = os.getenv("BGAI_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # In desktop mode or frozen executable, store in Windows AppData
    is_desktop = is_frozen() or os.getenv("BGAI_DESKTOP_MODE", "").lower() in ("1", "true", "yes")

    if is_desktop:
        appdata = os.getenv("APPDATA")
        if appdata:
            p = Path(appdata) / "BG_AI"
            p.mkdir(parents=True, exist_ok=True)
            return p
        # Fallback to user home
        p = Path.home() / ".bgai"
        p.mkdir(parents=True, exist_ok=True)
        return p

    # Default development mode: project root (parents[2] from app/paths.py)
    root = Path(__file__).resolve().parents[2]
    return root


def get_app_data_file(filename: str) -> Path:
    """
    Returns a full path to a file inside the persistent app data directory.
    If the file does not exist in AppData, or is an unpopulated SQLite schema (<= 20KB)
    while a populated seed exists in the application root or bundle, copies the seed.
    """
    data_dir = get_app_data_dir()
    file_path = data_dir / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Locate potential seed copies
    candidates: list[Path] = []
    # 1. PyInstaller frozen locations
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / filename)
            candidates.append(Path(meipass) / "backend" / filename)
        exe_dir = Path(sys.executable).parent
        candidates.append(exe_dir / filename)
        candidates.append(exe_dir / "_internal" / filename)
        candidates.append(exe_dir / "resources" / filename)
        candidates.append(exe_dir / "resources" / "backend" / filename)
        candidates.append(exe_dir / "resources" / "backend" / "_internal" / filename)

    # 2. Source root (development / repository root)
    root = Path(__file__).resolve().parents[2]
    candidates.append(root / filename)
    candidates.append(root / "backend" / filename)
    cwd = Path.cwd()
    candidates.append(cwd / filename)
    candidates.append(cwd / "backend" / filename)

    # Perform seeding if target is missing or empty
    if not file_path.exists():
        for cand in candidates:
            try:
                if cand.resolve() != file_path.resolve() and cand.is_file() and cand.stat().st_size > 0:
                    import shutil
                    shutil.copy2(cand, file_path)
                    break
            except Exception:
                continue
    elif filename.endswith(".db") and file_path.stat().st_size <= 20480:
        # File exists but is an unpopulated SQLite schema (20KB)
        for cand in candidates:
            try:
                if cand.resolve() != file_path.resolve() and cand.is_file() and cand.stat().st_size > file_path.stat().st_size:
                    import shutil
                    shutil.copy2(cand, file_path)
                    break
            except Exception:
                continue

    return file_path


def get_logs_dir() -> Path:
    """Returns the directory for application logs."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir

