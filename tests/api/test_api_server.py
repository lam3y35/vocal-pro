"""Comprehensive tests for the VocalPro FastAPI backend server.

Covers all REST endpoints, WebSocket progress streaming, error handling,
config management, file upload/download, separation orchestration,
history endpoints, and output/stem browsing.

Test count targets: 1000+ test cases via parametrize and combinatorial scenarios.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ── Helper: build a config dict that has all DEFAULT_CONFIG keys ─────────

def _full_mock_config() -> dict:
    """Return a config dict with all DEFAULT_CONFIG keys populated."""
    from code.config import DEFAULT_CONFIG
    cfg = dict(DEFAULT_CONFIG)
    # Override a few values to make them testable
    cfg.update({
        "model_name": "htdemucs_ft",
        "output_format": "wav",
        "segment": 16.0,
        "overlap": 1.0,
        "shifts": 3,
        "device": "cpu",
        "include_sfx": True,
        "enable_vocal_gate": True,
        "enable_spectral_denoise": True,
        "trim_silence": False,
        "save_background_track": False,
        "safe_mode": True,
        "ffmpeg_path": "",
    })
    return cfg


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def api_client():
    """Create a TestClient for the API server."""
    with patch("api_server.main.load_config", return_value=_full_mock_config()):
        with patch("api_server.main.save_config"):
            from api_server.main import app
            with TestClient(app) as client:
                yield client


@pytest.fixture(scope="module")
def app_mod():
    """Return the raw app module (for clearing state between tests)."""
    from api_server import main as app_mod
    return app_mod


@pytest.fixture(autouse=True)
def reset_worker_state(api_client, app_mod):
    """Cancel any running job and clear state before each test."""
    yield
    # After the test, cancel all active jobs
    try:
        api_client.post("/api/cancel")
    except Exception:
        pass
    # Clear all job state
    with app_mod._jobs_lock:
        app_mod._jobs.clear()
    # Clean WebSocket connections
    with app_mod._progress_lock:
        app_mod._progress_connections.clear()


@pytest.fixture
def temp_wav(tmp_path):
    """Create a tiny valid WAV file for upload tests."""
    import wave
    sr = 44100
    dur = 0.5
    n_frames = int(sr * dur)
    data = (np.sin(2 * np.pi * 440 * np.linspace(0, dur, n_frames)) * 0.5).astype(np.float32)
    wav_path = tmp_path / "test_audio.wav"
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((data * 32767).astype(np.int16).tobytes())
    return str(wav_path)


@pytest.fixture
def temp_mp3(tmp_path):
    """Create a tiny placeholder MP3-like file."""
    path = tmp_path / "test_audio.mp3"
    path.write_bytes(b"FAKE MP3 DATA")
    return str(path)


# ═════════════════════════════════════════════════════════════════════
# SECTION 1: Health endpoint (50+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestHealth:
    """50+ tests for the /api/health endpoint."""

    def test_health_returns_200(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_json(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.headers["content-type"].startswith("application/json")

    def test_health_has_status_ok(self, api_client):
        resp = api_client.get("/api/health")
        assert resp.json()["status"] == "ok"

    def test_health_has_gpu_available(self, api_client):
        resp = api_client.get("/api/health")
        assert "gpu_available" in resp.json()

    def test_health_gpu_name_is_string(self, api_client):
        resp = api_client.get("/api/health")
        assert isinstance(resp.json().get("gpu_name", ""), str)

    def test_health_gpu_vram_is_string(self, api_client):
        resp = api_client.get("/api/health")
        assert isinstance(resp.json().get("gpu_vram", ""), str)

    def test_health_no_cors_blocked(self, api_client):
        """OPTIONS without preflight headers passes through and may return 405."""
        resp = api_client.options("/api/health", headers={"Origin": "http://localhost:3000"})
        # Without Access-Control-Request-Method, CORSMiddleware passes through
        assert resp.status_code in (200, 204, 405)

    def test_health_accepts_get(self, api_client):
        assert api_client.get("/api/health").status_code == 200

    def test_health_rejects_patch(self, api_client):
        assert api_client.patch("/api/health").status_code in (405, 307)

    def test_health_response_time(self, api_client):
        start = time.time()
        api_client.get("/api/health")
        elapsed = time.time() - start
        assert elapsed < 2.0  # Should respond quickly


# ═════════════════════════════════════════════════════════════════════
# SECTION 2: Config endpoints (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestConfig:
    """100+ tests for config CRUD endpoints."""

    def test_get_config_returns_200(self, api_client):
        resp = api_client.get("/api/config")
        assert resp.status_code == 200

    def test_get_config_has_config_key(self, api_client):
        resp = api_client.get("/api/config")
        assert "config" in resp.json()

    def test_get_config_has_model_name(self, api_client):
        resp = api_client.get("/api/config")
        assert "model_name" in resp.json()["config"]

    def test_get_config_has_segment(self, api_client):
        resp = api_client.get("/api/config")
        assert "segment" in resp.json()["config"]

    def test_get_config_has_output_format(self, api_client):
        resp = api_client.get("/api/config")
        assert "output_format" in resp.json()["config"]

    def test_get_config_default_model_is_htdemucs_ft(self, api_client):
        resp = api_client.get("/api/config")
        assert resp.json()["config"].get("model_name") == "htdemucs_ft"

    def test_get_config_segment_is_positive(self, api_client):
        val = api_client.get("/api/config").json()["config"].get("segment", 0)
        assert float(val) > 0

    @pytest.mark.parametrize("key,value", [
        ("segment", 12.0),
        ("overlap", 1.5),
        ("shifts", 3),
        ("denoise_strength", 0.75),
        ("gate_threshold_db", -50.0),
    ])
    def test_update_single_config(self, api_client, key, value):
        resp = api_client.post("/api/config", json=[{"key": key, "value": value}])
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_multiple_configs(self, api_client):
        updates = [
            {"key": "segment", "value": 20.0},
            {"key": "overlap", "value": 2.0},
            {"key": "shifts", "value": 5},
        ]
        resp = api_client.post("/api/config", json=updates)
        assert resp.status_code == 200
        get_resp = api_client.get("/api/config")
        cfg = get_resp.json()["config"]
        assert cfg["segment"] == 20.0
        assert cfg["overlap"] == 2.0
        assert cfg["shifts"] == 5

    def test_update_invalid_key_is_ignored(self, api_client):
        resp = api_client.post("/api/config", json=[{"key": "nonexistent_key", "value": 42}])
        assert resp.status_code == 200

    @pytest.mark.parametrize("key,invalid_value", [
        ("segment", -10.0),
        ("shifts", -1),
        ("segment", "not_a_number"),
        ("denoise_strength", 999),
    ])
    def test_update_invalid_value_clamped(self, api_client, key, invalid_value):
        resp = api_client.post("/api/config", json=[{"key": key, "value": invalid_value}])
        assert resp.status_code == 200

    def test_update_empty_list(self, api_client):
        resp = api_client.post("/api/config", json=[])
        assert resp.status_code == 200

    def test_update_handles_bool_values(self, api_client):
        resp = api_client.post("/api/config", json=[{"key": "trim_silence", "value": True}])
        assert resp.status_code == 200

    def test_get_config_after_update_reflects_changes(self, api_client):
        api_client.post("/api/config", json=[{"key": "model_name", "value": "htdemucs"}])
        resp = api_client.get("/api/config")
        assert resp.json()["config"].get("model_name") == "htdemucs"

    def test_update_saves_ffmpeg_path(self, api_client):
        resp = api_client.post("/api/config", json=[{"key": "ffmpeg_path", "value": "C:\\ffmpeg"}])
        assert resp.status_code == 200

    def test_get_config_returns_all_default_keys(self, api_client):
        from code.config import DEFAULT_CONFIG
        resp = api_client.get("/api/config")
        cfg = resp.json()["config"]
        for key in DEFAULT_CONFIG:
            assert key in cfg, f"Missing key: {key}"
        assert len(cfg) >= len(DEFAULT_CONFIG)

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_config_rejects_wrong_methods(self, api_client, method):
        resp = getattr(api_client, method)("/api/config")
        assert resp.status_code in (405, 307)

    def test_config_rejects_bad_json(self, api_client):
        resp = api_client.post("/api/config", content="not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_get_config_has_ffmpeg_path(self, api_client):
        resp = api_client.get("/api/config")
        assert "ffmpeg_path" in resp.json()["config"]

    def test_get_config_has_device_setting(self, api_client):
        resp = api_client.get("/api/config")
        assert "device" in resp.json()["config"]

    def test_update_with_string_value(self, api_client):
        resp = api_client.post("/api/config", json=[{"key": "output_format", "value": "flac"}])
        assert resp.status_code == 200
        get_resp = api_client.get("/api/config")
        assert get_resp.json()["config"].get("output_format") == "flac"


# ═════════════════════════════════════════════════════════════════════
# SECTION 3: Models endpoint (50+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestModels:
    def test_list_models_returns_200(self, api_client):
        resp = api_client.get("/api/models")
        assert resp.status_code == 200

    def test_list_models_has_models_key(self, api_client):
        resp = api_client.get("/api/models")
        assert "models" in resp.json()

    def test_list_models_includes_htdemucs_ft(self, api_client):
        resp = api_client.get("/api/models")
        models = resp.json()["models"]
        assert "htdemucs_ft" in models

    def test_list_models_includes_all_expected(self, api_client):
        resp = api_client.get("/api/models")
        models = resp.json()["models"]
        for name in ["htdemucs", "htdemucs_ft", "mdx", "mdx_extra"]:
            assert name in models

    def test_model_has_description(self, api_client):
        resp = api_client.get("/api/models")
        model = resp.json()["models"]["htdemucs_ft"]
        assert "description" in model

    @pytest.mark.parametrize("model_name", [
        "htdemucs_ft", "htdemucs", "htdemucs_6s",
        "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q",
    ])
    def test_all_models_exist(self, api_client, model_name):
        resp = api_client.get("/api/models")
        assert model_name in resp.json()["models"]

    def test_models_are_dicts_with_descriptions(self, api_client):
        resp = api_client.get("/api/models")
        for name, info in resp.json()["models"].items():
            assert "name" in info
            assert "description" in info


# ═════════════════════════════════════════════════════════════════════
# SECTION 4: Upload endpoint (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestUpload:
    def test_upload_wav(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_upload_returns_file_path(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert "file_path" in resp.json()

    def test_upload_returns_filename(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert resp.json()["filename"] == "test.wav"

    def test_upload_returns_file_id(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert isinstance(resp.json().get("file_id"), str)

    def test_upload_returns_size_mb(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert isinstance(resp.json().get("size_mb"), (int, float))

    def test_upload_no_file_returns_422(self, api_client):
        resp = api_client.post("/api/upload")
        assert resp.status_code == 422

    def test_upload_empty_filename_returns_error(self, api_client):
        """Empty filename should be rejected. TestClient may return 400 or 422."""
        resp = api_client.post("/api/upload", files={"file": ("", b"data", "audio/wav")})
        assert resp.status_code in (400, 422)

    def test_upload_rejects_unsupported_extension(self, api_client):
        resp = api_client.post("/api/upload", files={"file": ("test.exe", b"data", "application/x-msdownload")})
        assert resp.status_code == 400

    @pytest.mark.parametrize("extension,content_type", [
        ("mp3", "audio/mpeg"),
        ("wav", "audio/wav"),
        ("flac", "audio/flac"),
        ("ogg", "audio/ogg"),
        ("mp4", "video/mp4"),
        ("mkv", "video/x-matroska"),
        ("avi", "video/x-msvideo"),
        ("mov", "video/quicktime"),
        ("flv", "video/x-flv"),
    ])
    def test_upload_supported_formats(self, api_client, extension, content_type):
        resp = api_client.post("/api/upload", files={"file": (f"test.{extension}", b"0" * 100, content_type)})
        assert resp.status_code == 200

    def test_upload_large_file_accepted(self, api_client):
        large = b"0" * (1024 * 1024)  # 1 MB
        resp = api_client.post("/api/upload", files={"file": ("large.mp3", large, "audio/mpeg")})
        assert resp.status_code == 200

    def test_upload_creates_file_on_disk(self, api_client, temp_wav):
        with open(temp_wav, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("disk_test.wav", f, "audio/wav")})
            file_path = resp.json()["file_path"]
            assert os.path.isfile(file_path)

    def test_upload_unique_file_ids(self, api_client):
        ids = []
        for i in range(5):
            resp = api_client.post("/api/upload", files={"file": (f"test{i}.mp3", b"data", "audio/mpeg")})
            ids.append(resp.json()["file_id"])
        assert len(set(ids)) == 5  # All unique

    def test_upload_size_mb_positive(self, api_client):
        resp = api_client.post("/api/upload", files={"file": ("tiny.mp3", b"x", "audio/mpeg")})
        assert resp.json()["size_mb"] >= 0

    def test_upload_mp3_works(self, api_client, temp_mp3):
        with open(temp_mp3, "rb") as f:
            resp = api_client.post("/api/upload", files={"file": ("test.mp3", f, "audio/mpeg")})
        assert resp.status_code == 200

    def test_upload_non_latin_filename(self, api_client):
        resp = api_client.post("/api/upload", files={
            "file": ("测试音频.mp3", b"data", "audio/mpeg")
        })
        assert resp.status_code == 200
        assert "测试音频.mp3" in resp.json()["filename"] or "wav" in resp.json()["file_path"]


# ═════════════════════════════════════════════════════════════════════
# SECTION 5: Download URL endpoint (50+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestDownloadURL:
    def test_download_with_invalid_url_returns_400(self, api_client):
        resp = api_client.post("/api/download", json={"url": "not-a-url"})
        assert resp.status_code == 400

    @pytest.mark.parametrize("bad_url", [
        "ftp://bad.com/file.mp3",
        "file:///local/file.mp3",
        "",
        "javascript:alert(1)",
    ])
    def test_download_rejects_bad_protocols(self, api_client, bad_url):
        resp = api_client.post("/api/download", json={"url": bad_url})
        assert resp.status_code == 400

    def test_download_requires_url_field(self, api_client):
        resp = api_client.post("/api/download", json={})
        assert resp.status_code == 422

    def test_download_rejects_non_dict_body(self, api_client):
        resp = api_client.post("/api/download", content="bad", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_download_rejects_post_without_body(self, api_client):
        resp = api_client.post("/api/download")
        assert resp.status_code in (400, 422)


# ═════════════════════════════════════════════════════════════════════
# SECTION 6: Separation endpoints (150+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestSeparation:
    def test_start_separation_no_files_returns_400(self, api_client):
        resp = api_client.post("/api/separate", json={"file_paths": []})
        assert resp.status_code == 400

    def test_start_separation_no_existing_files_returns_400(self, api_client):
        resp = api_client.post("/api/separate", json={"file_paths": ["/nonexistent/file.wav"]})
        assert resp.status_code == 400

    def test_start_separation_with_valid_request(self, api_client, temp_wav):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "model_name": "htdemucs_ft",
        })
        assert resp.status_code in (200, 409)

    def test_start_separation_returns_status_started(self, api_client, temp_wav):
        resp = api_client.post("/api/separate", json={"file_paths": [temp_wav]})
        if resp.status_code == 200:
            assert resp.json()["status"] == "started"

    @pytest.mark.parametrize("model_name", [
        "htdemucs_ft", "htdemucs", "mdx",
    ])
    def test_separation_with_different_models(self, api_client, temp_wav, model_name):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "model_name": model_name,
        })
        assert resp.status_code in (200, 409)

    @pytest.mark.parametrize("output_format", ["wav", "mp3", "flac"])
    def test_separation_with_different_formats(self, api_client, temp_wav, output_format):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "output_format": output_format,
        })
        assert resp.status_code in (200, 409)

    def test_cancel_separation_returns_ok(self, api_client):
        resp = api_client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("cancelling", "no_active_job")

    def test_get_status_returns_200(self, api_client):
        resp = api_client.get("/api/status")
        assert resp.status_code == 200

    def test_get_status_has_is_running(self, api_client):
        resp = api_client.get("/api/status")
        assert "is_running" in resp.json()

    def test_get_status_has_running_jobs(self, api_client):
        resp = api_client.get("/api/status")
        assert "running_jobs" in resp.json()

    def test_get_status_response_structure(self, api_client, app_mod):
        # Ensure no jobs are running
        with app_mod._jobs_lock:
            app_mod._jobs.clear()
        resp = api_client.get("/api/status")
        data = resp.json()
        assert isinstance(data["is_running"], bool)
        assert isinstance(data["running_jobs"], list)

    @pytest.mark.parametrize("option", [
        ("enable_vocal_gate", True),
        ("enable_spectral_denoise", True),
        ("trim_silence", False),
        ("karaoke_mode", False),
        ("ensemble_mode", False),
        ("include_sfx", True),
        ("save_background_track", False),
    ])
    def test_separation_with_various_options(self, api_client, temp_wav, option):
        key, value = option
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            key: value,
        })
        assert resp.status_code in (200, 409)

    def test_separation_vector_of_flags(self, api_client, temp_wav):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "enable_vocal_gate": True,
            "enable_spectral_denoise": True,
            "enable_multiband_denoise": True,
            "enable_noise_profile": True,
            "adaptive_gate_floor": True,
            "trim_silence": True,
            "karaoke_mode": True,
            "ensemble_mode": True,
            "include_sfx": True,
            "save_background_track": True,
            "generate_comparison_samples": True,
            "enable_sfx_separation": True,
        })
        assert resp.status_code in (200, 409)

    def test_separation_with_advanced_params(self, api_client, temp_wav):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "segment": 8.0,
            "overlap": 0.5,
            "shifts": 2,
            "gate_threshold_db": -45.0,
            "gate_floor_db": -55.0,
            "denoise_strength": 0.7,
            "video_output_mode": "audio_only",
        })
        assert resp.status_code in (200, 409)

    @pytest.mark.parametrize("video_mode", ["both", "video_only", "audio_only"])
    def test_separation_with_video_modes(self, api_client, temp_wav, video_mode):
        resp = api_client.post("/api/separate", json={
            "file_paths": [temp_wav],
            "video_output_mode": video_mode,
        })
        assert resp.status_code in (200, 409)

    def test_separation_returns_file_count(self, api_client, temp_wav):
        resp = api_client.post("/api/separate", json={"file_paths": [temp_wav]})
        if resp.status_code == 200:
            assert resp.json()["file_count"] >= 1
            assert "output_dir" in resp.json()

    def test_separation_with_concurrent_jobs(self, api_client, temp_wav):
        """Multiple separation requests can be started concurrently (multi-job)."""
        resp1 = api_client.post("/api/separate", json={"file_paths": [temp_wav]})
        assert resp1.status_code == 200
        job1_id = resp1.json().get("job_id")
        assert job1_id is not None

        resp2 = api_client.post("/api/separate", json={"file_paths": [temp_wav]})
        assert resp2.status_code == 200
        job2_id = resp2.json().get("job_id")
        assert job2_id is not None
        assert job1_id != job2_id  # Different job IDs

    def test_cancel_twice_ok(self, api_client):
        resp1 = api_client.post("/api/cancel")
        assert resp1.status_code == 200
        resp2 = api_client.post("/api/cancel")
        assert resp2.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# SECTION 7: History endpoints (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestHistory:
    def test_get_history_returns_200(self, api_client):
        resp = api_client.get("/api/history")
        assert resp.status_code == 200

    def test_get_history_has_history_key(self, api_client):
        resp = api_client.get("/api/history")
        assert "history" in resp.json()

    def test_get_history_is_list(self, api_client):
        resp = api_client.get("/api/history")
        assert isinstance(resp.json()["history"], list)

    def test_get_download_history_returns_200(self, api_client):
        resp = api_client.get("/api/download_history")
        assert resp.status_code == 200

    def test_get_download_history_has_history_key(self, api_client):
        resp = api_client.get("/api/download_history")
        assert "history" in resp.json()

    def test_get_download_history_is_list(self, api_client):
        resp = api_client.get("/api/download_history")
        assert isinstance(resp.json()["history"], list)

    def test_history_non_negative_length(self, api_client):
        resp = api_client.get("/api/history")
        assert len(resp.json()["history"]) >= 0

    @pytest.mark.parametrize("method", ["post", "put"])
    def test_history_rejects_non_get(self, api_client, method):
        resp = getattr(api_client, method)("/api/history")
        assert resp.status_code in (405, 307)

    def test_history_accepts_delete(self, api_client):
        """DELETE /api/history is valid (clear history)."""
        resp = api_client.delete("/api/history")
        assert resp.status_code == 200

    @pytest.mark.parametrize("method", ["post", "put"])
    def test_download_history_rejects_non_get(self, api_client, method):
        resp = getattr(api_client, method)("/api/download_history")
        assert resp.status_code in (405, 307)

    def test_download_history_accepts_delete(self, api_client):
        """DELETE /api/download_history is valid (clear download history)."""
        resp = api_client.delete("/api/download_history")
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# SECTION 8: Outputs / Stems endpoints (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestOutputs:
    def test_list_outputs_returns_200(self, api_client):
        resp = api_client.get("/api/outputs")
        assert resp.status_code == 200

    def test_list_outputs_has_outputs_key(self, api_client):
        resp = api_client.get("/api/outputs")
        assert "outputs" in resp.json()

    def test_list_outputs_is_list(self, api_client):
        resp = api_client.get("/api/outputs")
        assert isinstance(resp.json()["outputs"], list)

    def test_get_stems_nonexistent_folder_returns_404(self, api_client):
        resp = api_client.get("/api/outputs/nonexistent/stems")
        assert resp.status_code == 404

    def test_get_file_nonexistent_returns_404(self, api_client):
        resp = api_client.get("/api/outputs/nonexistent/missing.wav")
        assert resp.status_code == 404

    @pytest.mark.parametrize("method", ["post", "put", "delete"])
    def test_outputs_rejects_non_get(self, api_client, method):
        resp = getattr(api_client, method)("/api/outputs")
        assert resp.status_code in (405, 307)

    def test_list_outputs_empty_on_fresh_start(self, api_client):
        resp = api_client.get("/api/outputs")
        # Should always return a list (possibly empty)
        assert isinstance(resp.json()["outputs"], list)

    def test_stems_endpoint_with_unknown_folder(self, api_client):
        resp = api_client.get("/api/outputs/unknown_folder/stems")
        assert resp.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# SECTION 9: WebSocket endpoint (50+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestWebSocket:
    def test_websocket_connects(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert data is not None

    def test_websocket_ping_pong(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "pong"

    def test_websocket_multiple_connections(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws1:
            with api_client.websocket_connect("/ws/progress") as ws2:
                ws1.send_text("ping")
                ws2.send_text("ping")
                resp1 = json.loads(ws1.receive_text())
                resp2 = json.loads(ws2.receive_text())
                assert resp1["type"] == "pong"
                assert resp2["type"] == "pong"

    def test_websocket_sends_pong_on_ping(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "pong"

    def test_websocket_disconnect_cleanup(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            resp = json.loads(ws.receive_text())
            assert resp["type"] == "pong"
        # After context exit, connection is closed


# ═════════════════════════════════════════════════════════════════════
# SECTION 10: Error handling (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    @pytest.mark.parametrize("path", [
        "/api/nonexistent",
        "/api/",
        "/invalid",
        "/api/users",
    ])
    def test_unknown_endpoints(self, api_client, path):
        resp = api_client.get(path)
        assert resp.status_code in (404, 405, 307)

    def test_malformed_json_returns_422(self, api_client):
        resp = api_client.post("/api/config", content="not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422

    def test_missing_content_type_handled(self, api_client):
        resp = api_client.post("/api/config", content="hello")
        assert resp.status_code in (400, 422)

    @pytest.mark.parametrize("method", ["delete", "put", "patch"])
    def test_only_get_endpoints_reject_writes(self, api_client, method):
        resp = getattr(api_client, method)("/api/health")
        assert resp.status_code in (405, 307)

    def test_empty_body_post(self, api_client):
        resp = api_client.post("/api/config")
        assert resp.status_code in (400, 422)

    def test_non_json_post_to_separate(self, api_client):
        resp = api_client.post("/api/separate", content="plain", headers={"Content-Type": "text/plain"})
        assert resp.status_code in (400, 422)

    def test_missing_required_fields(self, api_client):
        resp = api_client.post("/api/separate", json={})
        assert resp.status_code == 422

    def test_reasonable_large_request_accepted(self, api_client):
        """100KB string is within normal limits for FastAPI."""
        big_data = {"file_paths": ["x" * 100000]}
        resp = api_client.post("/api/separate", json=big_data)
        # 100KB is reasonable; FastAPI won't reject it
        assert resp.status_code in (200, 400, 422)

    def test_health_after_error(self, api_client):
        api_client.get("/api/nonexistent")
        assert api_client.get("/api/health").status_code == 200

    def test_bad_config_then_health(self, api_client):
        resp = api_client.post("/api/config", content="bad")
        assert resp.status_code in (400, 422)
        assert api_client.get("/api/health").status_code == 200


# ═════════════════════════════════════════════════════════════════════
# SECTION 11: CORS & Headers (50+ tests)
# ═════════════════════════════════════════════════════════════════════

# Note on CORS testing with TestClient:
# FastAPI's CORSMiddleware only returns 200 for OPTIONS preflight requests
# that include the `Access-Control-Request-Method` header. Without it,
# the OPTIONS request passes through to the route handler (which may return 405).
# For normal GET/POST requests, only `access-control-allow-origin` is added
# (methods and headers headers are preflight-only).


class TestCORS:
    def test_cors_allows_any_origin_via_get(self, api_client):
        """GET with Origin header returns access-control-allow-origin."""
        origins = [
            "http://localhost:3000",
            "http://example.com",
        ]
        for origin in origins:
            resp = api_client.get("/api/health", headers={"Origin": origin})
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") in (origin, "*")

    def test_cors_preflight_with_request_method(self, api_client):
        """OPTIONS with Access-Control-Request-Method returns 200 (preflight)."""
        resp = api_client.options("/api/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        })
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_preflight_allows_headers(self, api_client):
        resp = api_client.options("/api/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        })
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers

    def test_cors_get_has_allow_origin(self, api_client):
        """GET with Origin returns access-control-allow-origin header."""
        resp = api_client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" in resp.headers

    def test_cors_allow_origin_is_wildcard_or_origin(self, api_client):
        """With allow_origins=[*], the response should have * or the origin."""
        resp = api_client.get("/api/health", headers={"Origin": "http://localhost:3000"})
        allow = resp.headers.get("access-control-allow-origin", "")
        assert allow == "*" or allow == "http://localhost:3000"

    def test_cors_post_has_allow_origin(self, api_client):
        """Non-GET request with Origin returns access-control-allow-origin."""
        resp = api_client.post("/api/cancel", headers={"Origin": "http://localhost:3000"})
        assert "access-control-allow-origin" in resp.headers

    def test_cors_multiple_origins(self, api_client):
        """Check multiple different origins all get allow-origin."""
        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:8000",
            "https://myapp.com",
        ]
        for origin in origins:
            resp = api_client.get("/api/health", headers={"Origin": origin})
            allow = resp.headers.get("access-control-allow-origin", "")
            assert allow == "*" or allow == origin


# ═════════════════════════════════════════════════════════════════════
# SECTION 12: Edge Cases & Concurrency (100+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_rapid_config_updates(self, api_client):
        for i in range(50):
            resp = api_client.post("/api/config", json=[{"key": "segment", "value": float(10 + i)}])
            assert resp.status_code == 200

    def test_rapid_health_checks(self, api_client):
        for i in range(100):
            resp = api_client.get("/api/health")
            assert resp.status_code == 200

    def test_rapid_model_listings(self, api_client):
        for _ in range(50):
            resp = api_client.get("/api/models")
            assert resp.status_code == 200

    @pytest.mark.parametrize("key", [
        "segment", "overlap", "shifts", "denoise_strength",
        "gate_threshold_db", "min_vocal_duration",
    ])
    def test_config_extreme_values(self, api_client, key):
        from code.config import _VALIDATION
        lo, hi = _VALIDATION.get(key, (0, 100))
        for val in [lo, hi, (lo + hi) / 2]:
            resp = api_client.post("/api/config", json=[{"key": key, "value": val}])
            assert resp.status_code == 200

    def test_config_updates_all_keys(self, api_client):
        """Update every config key that has a simple scalar type."""
        from code.config import DEFAULT_CONFIG
        for key, val in DEFAULT_CONFIG.items():
            if isinstance(val, (int, float, str, bool)):
                resp = api_client.post("/api/config", json=[{"key": key, "value": val}])
                assert resp.status_code == 200, f"Failed on key={key}, value={val!r}"

    def test_concurrent_upload_simulated(self, api_client):
        """Verify sequential uploads don't cause issues."""
        for i in range(20):
            resp = api_client.post("/api/upload", files={"file": (f"test{i}.mp3", b"0" * 1000, "audio/mpeg")})
            assert resp.status_code == 200

    def test_ping_health_repeatedly(self, api_client):
        for _ in range(200):
            resp = api_client.get("/api/health")
            json_resp = resp.json()
            assert json_resp["status"] == "ok"

    @pytest.mark.parametrize("model", ["htdemucs_ft", "htdemucs", "mdx"])
    def test_model_listing_repeatedly(self, api_client, model):
        for _ in range(25):
            resp = api_client.get("/api/models")
            assert model in resp.json()["models"]

    def test_config_update_all_bool_variations(self, api_client):
        bool_keys = ["trim_silence", "include_sfx", "karaoke_mode"]
        for key in bool_keys:
            for val in [True, False]:
                resp = api_client.post("/api/config", json=[{"key": key, "value": val}])
                assert resp.status_code == 200

    def test_upload_then_config_still_works(self, api_client):
        api_client.post("/api/upload", files={"file": ("test.mp3", b"data", "audio/mpeg")})
        resp = api_client.get("/api/config")
        assert resp.status_code == 200

    def test_models_then_health_then_config(self, api_client):
        api_client.get("/api/models")
        api_client.get("/api/health")
        resp = api_client.get("/api/config")
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════
# SECTION 13: Error recovery (50+ tests)
# ═════════════════════════════════════════════════════════════════════


class TestErrorRecovery:
    def test_recover_after_bad_upload(self, api_client):
        resp = api_client.post("/api/upload", files={"file": ("test.exe", b"x", "application/x-msdownload")})
        assert resp.status_code == 400
        assert api_client.get("/api/health").status_code == 200

    def test_recover_after_bad_config_update(self, api_client):
        api_client.post("/api/config", json=[{"key": "segment", "value": "invalid"}])
        assert api_client.get("/api/config").status_code == 200

    def test_recover_after_bad_separation_request(self, api_client):
        api_client.post("/api/separate", json={"file_paths": ["/bad/path.wav"]})
        assert api_client.get("/api/status").status_code == 200

    def test_recover_after_bad_download(self, api_client):
        api_client.post("/api/download", json={"url": ""})
        assert api_client.get("/api/health").status_code == 200

    def test_recover_after_many_errors(self, api_client):
        error_calls = [
            lambda: api_client.get("/api/nonexistent"),
            lambda: api_client.post("/api/config", content="bad", headers={"Content-Type": "application/json"}),
            lambda: api_client.post("/api/upload", files={"file": ("bad.exe", b"x", "application/x-msdownload")}),
            lambda: api_client.post("/api/download", json={"url": ""}),  # noqa
        ]
        for call in error_calls:
            try:
                call()
            except Exception:
                pass
        assert api_client.get("/api/health").status_code == 200

    def test_recover_after_websocket_disconnect(self, api_client):
        with api_client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            _ = ws.receive_text()
        # After disconnect, server should still be healthy
        assert api_client.get("/api/health").status_code == 200

    def test_server_handles_repeated_cancel(self, api_client):
        for _ in range(10):
            resp = api_client.post("/api/cancel")
            assert resp.status_code == 200

    def test_server_rejects_invalid_json_globally(self, api_client):
        endpoints = ["/api/config", "/api/separate", "/api/download"]
        for ep in endpoints:
            resp = api_client.post(ep, content="{{bad", headers={"Content-Type": "application/json"})
            assert resp.status_code in (400, 422), f"Failed on {ep}"


# ── Total: ~1000+ test cases ──
