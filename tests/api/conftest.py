"""Pytest fixtures for API server tests — FastAPI TestClient with mocked dependencies."""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


@pytest.fixture(autouse=True)
def mock_torch():
    """Mock torch module in sys.modules (torch is imported inside function scope)."""
    import types as _types

    mock = _types.ModuleType("torch")
    mock.__version__ = "0.0.0"
    mock.__file__ = "<mocked>"

    # Use MagicMock for torch.cuda so tests can assign return_value
    mock_cuda = MagicMock()
    mock_cuda.is_available.return_value = False
    mock_cuda.get_device_name.return_value = ""
    props = MagicMock()
    props.total_mem = 0
    props.major = 0
    props.minor = 0
    mock_cuda.get_device_properties.return_value = props
    mock_cuda.empty_cache.return_value = None
    mock.cuda = mock_cuda

    sys.modules["torch"] = mock
    sys.modules["torch.cuda"] = mock_cuda
    yield mock


@pytest.fixture
def mock_librosa():
    """Mock librosa to avoid audio file loading."""
    import numpy as np

    with patch("api_server.main.librosa") as mock:
        # Default: return a simple sine tone
        sr = 22050
        duration = 1.0
        t = np.linspace(0, duration, int(sr * duration), 0)
        y = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        mock.load.return_value = (y, sr)
        mock.beat.beat_track.return_value = (120.0, np.array([0, 1, 2]))
        mock.feature.chroma_cqt.return_value = np.random.rand(12, 100)
        mock.onset.onset_detect.return_value = np.array([0, 10, 20])
        mock.frames_to_time.side_effect = lambda frames, sr: frames.astype(float) / sr
        mock.times_like.return_value = np.linspace(0, duration, len(y))
        mock.note_to_hz.side_effect = lambda n: {"C2": 65.41, "C7": 2093.0}.get(n, 440.0)
        # pyin return shapes must match times_like output (len(y) = 22050)
        n_frames = len(y)
        mock.pyin.return_value = (
            np.full(n_frames, 440.0, dtype=np.float32),
            np.ones(n_frames, dtype=bool),
            np.ones(n_frames, dtype=float),
        )
        yield mock


@pytest.fixture
def mock_soundfile():
    """Mock only sf.read; keep sf.write working for preview/export/MIDI endpoints."""
    import numpy as np

    with patch("api_server.main.sf.read") as mock_read:
        mock_read.return_value = (np.random.randn(44100, 2).astype(np.float32), 44100)
        yield mock_read


@pytest.fixture(autouse=True)
def mock_separation_engine():
    """Mock the entire code.separation_engine module to prevent heavy imports
    (torch, torchaudio, demucs, librosa) that crash on broken torch installs.

    SeparationEngine is imported inside _worker() via:
        from code.separation_engine import SeparationEngine

    By inserting a fake module into sys.modules, we avoid ever importing the
    real module, which would trigger torch/torchaudio/demucs at module level.
    """
    import types as _types

    mock_mod = _types.ModuleType("code.separation_engine")
    mock_mod.__file__ = "<mocked>"
    mock_mod.__package__ = "code.separation_engine"
    mock_mod.__path__ = []

    # Mock the SeparationEngine class
    engine_instance = MagicMock()
    engine_instance.separate_file.return_value = "/fake/output/folder"
    engine_instance.sample_rate = 44100
    engine_instance.device = "cpu"

    mock_mod.SeparationEngine = MagicMock(return_value=engine_instance)
    mock_mod.MODEL_POOL = frozenset({"htdemucs_ft", "htdemucs", "mdx"})
    mock_mod.MODEL_CACHE = {}
    mock_mod.MODEL_CACHE_LOCK = MagicMock()
    mock_mod._remove_with_retry = MagicMock()

    sys.modules["code.separation_engine"] = mock_mod
    yield mock_mod
    # Clean up after the test so other test modules (e.g. those testing
    # separation_engine directly) can still import the real module.
    sys.modules.pop("code.separation_engine", None)


@pytest.fixture
def client(mock_torch, mock_librosa, mock_soundfile, mock_separation_engine, tmp_path):
    """FastAPI TestClient with all mocks applied and isolated temp directories."""
    from code.config import DEFAULT_CONFIG
    from api_server.main import app, _progress_connections

    # Override globals with temp paths
    import api_server.main as api_module

    # Save originals
    _orig_upload = api_module.UPLOAD_DIR
    _orig_output = api_module.OUTPUT_DIR

    api_module.UPLOAD_DIR = str(tmp_path / "uploads")
    api_module.OUTPUT_DIR = str(tmp_path / "outputs")
    os.makedirs(api_module.UPLOAD_DIR, exist_ok=True)
    os.makedirs(api_module.OUTPUT_DIR, exist_ok=True)

    # Clear progress connections
    _progress_connections.clear()

    # Wire config to a temp file so tests are isolated from real user config
    import api_server.main as api_main_mod
    import json
    cfg_path = tmp_path / "config.json"
    with open(str(cfg_path), "w") as f:
        json.dump(dict(DEFAULT_CONFIG), f)

    # Replace load_config/save_config in the api_server.main module to use the temp file
    _orig_load = api_main_mod.load_config
    _orig_save = api_main_mod.save_config

    def _temp_load():
        if cfg_path.exists():
            with open(str(cfg_path)) as f:
                user = json.load(f)
        else:
            user = {}
        from code.config import DEFAULT_CONFIG as _dc
        from code.config import _validate
        cfg = dict(_dc)
        cfg.update(user)
        return _validate(cfg)

    def _temp_save(cfg):
        from code.config import _validate
        validated = _validate(cfg)
        with open(str(cfg_path), "w") as f:
            json.dump(validated, f, indent=2, default=str)

    api_main_mod.load_config = _temp_load
    api_main_mod.save_config = _temp_save

    with TestClient(app) as c:
        yield c

    # Restore
    api_main_mod.load_config = _orig_load
    api_main_mod.save_config = _orig_save
    api_module.UPLOAD_DIR = _orig_upload
    api_module.OUTPUT_DIR = _orig_output


@pytest.fixture
def sample_wav(tmp_path):
    """Create a small fake WAV file for upload tests."""
    import numpy as np
    import soundfile as sf

    path = str(tmp_path / "test_sine.wav")
    sr = 44100
    t = np.linspace(0, 0.5, int(sr * 0.5), 0)
    data = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    sf.write(path, data, sr)
    return path


@pytest.fixture
def sample_output_dir(tmp_path, client):
    """Create a fake output directory with stem files for testing."""
    import numpy as np
    import soundfile as sf

    from api_server.main import OUTPUT_DIR

    folder = os.path.join(OUTPUT_DIR, "test_output")
    os.makedirs(folder, exist_ok=True)
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), 0)
    for stem in ["vocals", "drums", "bass", "other"]:
        data = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        sf.write(os.path.join(folder, f"{stem}.wav"), data, sr)
    return folder
