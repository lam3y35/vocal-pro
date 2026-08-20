"""Pytest configuration and shared fixtures for VocalPro."""

import sys
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ── PyArrow workaround ──────────────────────────────────────────────────
if "pyarrow" not in sys.modules:
    _mock_pa = types.ModuleType("pyarrow")
    _mock_pa.__version__ = "0.0.0"
    _mock_pa.__file__ = "<mocked>"
    _mock_pa.__path__ = []
    _mock_pa.__package__ = "pyarrow"
    sys.modules["pyarrow"] = _mock_pa


# ── Shared fixtures ────────────────────────────────────────────────────

@pytest.fixture
def stereo_signal():
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), 0)
    a = np.zeros((2, len(t)), dtype=np.float32)
    a[0] = np.sin(2 * np.pi * 440 * t) * 0.5
    a[1] = a[0].copy()
    return a, sr

@pytest.fixture
def mono_signal():
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), 0)
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32), sr

@pytest.fixture
def silent_signal():
    return np.zeros((2, 22050), dtype=np.float32), 44100

@pytest.fixture
def cfg():
    from code.config import DEFAULT_CONFIG
    return dict(DEFAULT_CONFIG)

@pytest.fixture
def engine(cfg):
    with patch("code.separation_engine.demucs_get_model") as m:
        mdl = MagicMock()
        mdl.sources = ["vocals", "other", "bass", "drums"]
        mdl.eval.return_value = None
        mdl.to.return_value = mdl
        m.return_value = mdl
        from code.separation_engine import SeparationEngine
        return SeparationEngine(cfg, progress_callback=lambda p, msg: None)


