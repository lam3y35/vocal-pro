"""Additional tests: migration from old config filename and edge-case validation.

Covers:
- Migration moves .vocal_remover_pro_config.json -> .vocalpro_config.json at import time
- Migration gracefully handles shutil.move failures (no exception raised)
- Numeric config keys with complex types (lists/dicts) reset to defaults
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest


def _import_fresh_module():
    """Import a fresh copy of code.config (remove from sys.modules first)."""
    if "code.config" in sys.modules:
        del sys.modules["code.config"]
    return importlib.import_module("code.config")


def test_migrates_old_config_file(tmp_path, monkeypatch):
    # Point HOME/USERPROFILE to a temporary dir so Path.home() resolves there
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    old = tmp_path / ".vocal_remover_pro_config.json"
    new = tmp_path / ".vocalpro_config.json"

    # Write a simple JSON payload to the old location
    old.write_text(json.dumps({"segment": 8.0}), encoding="utf-8")
    assert old.exists()
    if new.exists():
        new.unlink()

    mod = _import_fresh_module()

    # After import, migration should have moved the file
    assert old.exists() is False
    assert new.exists() is True

    # Contents preserved
    data = json.loads(new.read_text(encoding="utf-8"))
    assert data.get("segment") == 8.0


def test_migration_move_failure_logs_and_continues(tmp_path, monkeypatch):
    # Simulate shutil.move raising OSError during migration
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    old = tmp_path / ".vocal_remover_pro_config.json"
    new = tmp_path / ".vocalpro_config.json"

    old.write_text(json.dumps({"shifts": 2}), encoding="utf-8")
    assert old.exists()
    if new.exists():
        new.unlink()

    # Force shutil.move to raise
    def _fail_move(src, dst):
        raise OSError("simulated failure")

    monkeypatch.setattr(shutil, "move", _fail_move)

    # Import should not raise despite move failure
    mod = _import_fresh_module()

    # Because move failed, old file should still exist and new should not
    assert old.exists() is True
    assert new.exists() is False


def test_validate_resets_on_complex_types():
    # Complex types (list/dict) for numeric keys should be reset to DEFAULT_CONFIG
    mod = importlib.import_module("code.config")
    DEFAULT = mod.DEFAULT_CONFIG

    out = mod._validate({"segment": [1, 2, 3]})
    assert out["segment"] == DEFAULT["segment"]

    out2 = mod._validate({"shifts": {"a": 1}})
    assert out2["shifts"] == DEFAULT["shifts"]
