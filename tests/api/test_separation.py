"""Tests for /api/separate, /api/cancel, /api/status endpoints."""

from __future__ import annotations

import os


class TestSeparation:
    def test_separate_empty_file_list(self, client):
        resp = client.post("/api/separate", json={"file_paths": []})
        assert resp.status_code == 400
        assert "valid files" in resp.text.lower()

    def test_separate_nonexistent_file(self, client):
        resp = client.post("/api/separate", json={"file_paths": ["/nonexistent/file.wav"]})
        assert resp.status_code == 400
        assert "valid files" in resp.text.lower()

    def test_separate_starts_worker(self, client, sample_wav):
        resp = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "started"
        assert data["file_count"] == 1
        assert "output_dir" in data

    def test_separate_multiple_files(self, client, sample_wav, tmp_path):
        # Create a second sample
        import numpy as np
        import soundfile as sf

        p2 = os.path.join(str(tmp_path), "test2.wav")
        sf.write(p2, np.random.randn(22050).astype(np.float32), 22050)

        resp = client.post("/api/separate", json={"file_paths": [sample_wav, p2]})
        assert resp.status_code == 200
        assert resp.json()["file_count"] == 2

    def test_separate_custom_output_dir(self, client, sample_wav, tmp_path):
        out = str(tmp_path / "custom_out")
        resp = client.post("/api/separate", json={
            "file_paths": [sample_wav],
            "output_dir": out,
        })
        assert resp.status_code == 200
        assert os.path.isdir(out)

    def test_separate_with_model(self, client, sample_wav):
        resp = client.post("/api/separate", json={
            "file_paths": [sample_wav],
            "model_name": "mdx_extra",
        })
        assert resp.status_code == 200

    def test_separate_with_all_options(self, client, sample_wav):
        resp = client.post("/api/separate", json={
            "file_paths": [sample_wav],
            "enable_vocal_gate": False,
            "enable_spectral_denoise": False,
            "enable_multiband_denoise": True,
            "enable_noise_profile": False,
            "adaptive_gate_floor": True,
            "trim_silence": True,
            "karaoke_mode": False,
            "ensemble_mode": False,
            "include_sfx": True,
            "save_background_track": False,
            "generate_comparison_samples": False,
            "enable_sfx_separation": True,
            "segment": 16.0,
            "overlap": 1.0,
            "shifts": 3,
        })
        assert resp.status_code == 200

    def test_separate_video_output_modes(self, client, sample_wav):
        for mode in ["both", "video_only", "audio_only"]:
            resp = client.post("/api/separate", json={
                "file_paths": [sample_wav],
                "video_output_mode": mode,
            })
            assert resp.status_code == 200, f"mode={mode} failed"


class TestStatus:
    def test_status_not_running(self, client):
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "is_running" in data
        assert "running_jobs" in data

    def test_status_structure(self, client):
        data = client.get("/api/status").json()
        assert isinstance(data["is_running"], bool)
        assert isinstance(data["running_jobs"], list)


class TestCancel:
    def test_cancel_returns_ok(self, client):
        resp = client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("cancelling", "no_active_job")

    def test_cancel_twice(self, client):
        resp1 = client.post("/api/cancel")
        resp2 = client.post("/api/cancel")
        assert resp1.status_code == 200
        assert resp2.status_code == 200

    def test_cancel_with_job(self, client, sample_wav):
        """Start a job then cancel it — verify the cancel response."""
        resp = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp.status_code == 200

        resp = client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("cancelling", "no_active_job")

    def test_cancel_method_not_allowed(self, client):
        resp = client.get("/api/cancel")
        assert resp.status_code in (405,)


class TestRerun:
    def test_rerun_aliases_separate(self, client, sample_wav):
        resp = client.post("/api/rerun", json={"file_paths": [sample_wav]})
        assert resp.status_code == 200
        assert resp.json()["status"] == "started"

    def test_rerun_empty(self, client):
        resp = client.post("/api/rerun", json={"file_paths": []})
        assert resp.status_code == 400
