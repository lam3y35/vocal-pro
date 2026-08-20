"""Shared constants, paths, and utility functions for VocalPro.

Paths and directories are lazily initialized on first access to avoid
side effects at import time (better testability, faster startup).
"""

from __future__ import annotations

import os
import shutil
import sys


# ── Lazy Initialization ──────────────────────────────────────────────────

_INITIALIZED = False


def _ensure_dirs() -> None:
    """Create required data directories and migrate legacy files (idempotent)."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    os.makedirs(_DATA_DIR, exist_ok=True)
    os.makedirs(_PRESETS_DIR, exist_ok=True)

    # Migrate legacy files from app dir to data dir
    for name in ("download_history.json", "separation_history.json"):
        old = os.path.join(_APP_DIR, name)
        new = os.path.join(_DATA_DIR, name)
        if os.path.isfile(old) and not os.path.isfile(new):
            try:
                shutil.copy2(old, new)
            except Exception:
                pass


# ── Paths ────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _APP_DIR = os.path.dirname(sys.executable)
else:
    _APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_APP_DIR)

_APP_ICON = os.path.join(_PROJECT_ROOT, "vocalpro.ico")

_DATA_DIR = os.environ.get("APPDATA", os.path.expanduser("~"))
_DATA_DIR = os.path.join(_DATA_DIR, "VocalPro")

_HISTORY_FILE = os.path.join(_DATA_DIR, "download_history.json")
_SEP_HISTORY_FILE = os.path.join(_DATA_DIR, "separation_history.json")
_PRESETS_DIR = os.path.join(_DATA_DIR, "presets")

# Ensure data directories exist on first import (idempotent guard prevents
# redundant filesystem operations on re-import / during tests).
_ensure_dirs()

# ── Supported extensions ─────────────────────────────────────────────────
_SUPPORTED_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".mp3", ".wav", ".flac", ".ogg"}

