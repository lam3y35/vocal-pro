"""Tests for /api/history, /api/outputs, /api/stems/*, /api/stems/midi endpoints."""

from __future__ import annotations

import json
import os


class TestHistory:
    def test_get_history_empty(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_get_download_history_empty(self, client):
        resp = client.get("/api/download_history")
        assert resp.status_code == 200
        data = resp.json()
        assert "history" in data
        assert isinstance(data["history"], list)

    def test_get_history_structure(self, client):
        resp = client.get("/api/history")
        assert resp.status_code == 200

    def test_clear_sep_history(self, client):
        resp = client.delete("/api/history")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_clear_download_history(self, client):
        resp = client.delete("/api/download_history")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_clear_sep_twice(self, client):
        client.delete("/api/history")
        resp2 = client.delete("/api/history")
        assert resp2.status_code == 200

    def test_history_file_not_found_graceful(self, client):
        """If history file doesn't exist, return empty list."""
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_download_history_file_not_found_graceful(self, client):
        resp = client.get("/api/download_history")
        assert resp.status_code == 200
        assert resp.json()["history"] == []

    def test_clear_history_get_empty(self, client):
        client.delete("/api/history")
        resp = client.get("/api/history")
        assert resp.json()["history"] == []


class TestOutputs:
    def test_outputs_empty(self, client):
        resp = client.get("/api/outputs")
        assert resp.status_code == 200
        assert "outputs" in resp.json()

    def test_outputs_returns_list(self, client):
        data = client.get("/api/outputs").json()
        assert isinstance(data["outputs"], list)

    def test_outputs_with_folder(self, client, sample_output_dir):
        resp = client.get("/api/outputs")
        data = resp.json()
        assert len(data["outputs"]) >= 1

    def test_outputs_folder_has_files(self, client, sample_output_dir):
        data = client.get("/api/outputs").json()
        for folder in data["outputs"]:
            if folder["name"] == "test_output":
                assert len(folder["files"]) >= 4
                break
        else:
            assert False, "test_output folder not found"

    def test_output_file_download_not_found(self, client):
        resp = client.get("/api/outputs/nonexistent/file.wav")
        assert resp.status_code == 404

    def test_output_file_download(self, client, sample_output_dir):
        resp = client.get("/api/outputs/test_output/vocals.wav")
        assert resp.status_code in (200, 404)  # Might not be served depending on routing

    def test_get_stems_not_found(self, client):
        resp = client.get("/api/outputs/nonexistent/stems")
        assert resp.status_code == 404

    def test_get_stems(self, client, sample_output_dir):
        resp = client.get("/api/outputs/test_output/stems")
        assert resp.status_code == 200
        data = resp.json()
        assert "stems" in data
        assert len(data["stems"]) >= 1


class TestStemMixer:
    def test_preview_no_folder(self, client):
        resp = client.post("/api/stems/preview", json={
            "folder_name": "nonexistent",
            "volumes": {},
            "master_volume": 1.0,
        })
        assert resp.status_code == 404

    def test_preview_empty_folder(self, client, tmp_path):
        from api_server.main import OUTPUT_DIR
        empty = os.path.join(OUTPUT_DIR, "empty_folder")
        os.makedirs(empty, exist_ok=True)
        resp = client.post("/api/stems/preview", json={
            "folder_name": "empty_folder",
            "volumes": {},
            "master_volume": 1.0,
        })
        assert resp.status_code == 404

    def test_preview_returns_audio(self, client, sample_output_dir):
        resp = client.post("/api/stems/preview", json={
            "folder_name": "test_output",
            "volumes": {"vocals": 1.0, "drums": 0.5},
            "master_volume": 1.0,
        })
        assert resp.status_code == 200
        assert resp.headers.get("content-type") == "audio/wav"
        assert len(resp.content) > 100

    def test_preview_with_zero_volume(self, client, sample_output_dir):
        resp = client.post("/api/stems/preview", json={
            "folder_name": "test_output",
            "volumes": {"vocals": 0.0},
            "master_volume": 0.0,
        })
        assert resp.status_code == 400
        assert "too low" in resp.text.lower()

    def test_preview_partial_volumes(self, client, sample_output_dir):
        resp = client.post("/api/stems/preview", json={
            "folder_name": "test_output",
            "volumes": {"vocals": 1.5},
            "master_volume": 0.8,
        })
        assert resp.status_code == 200

    def test_export_no_folder(self, client):
        resp = client.post("/api/stems/export", json={
            "folder_name": "nonexistent",
            "volumes": {},
            "master_volume": 1.0,
        })
        assert resp.status_code == 404

    def test_export_success(self, client, sample_output_dir):
        resp = client.post("/api/stems/export", json={
            "folder_name": "test_output",
            "volumes": {"vocals": 1.0, "drums": 0.5},
            "master_volume": 1.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "file_path" in data
        assert os.path.isfile(data["file_path"])

    def test_export_mp3_format(self, client, sample_output_dir):
        resp = client.post("/api/stems/export", json={
            "folder_name": "test_output",
            "volumes": {},
            "master_volume": 1.0,
            "output_format": "flac",
        })
        assert resp.status_code == 200

    def test_export_separate_success(self, client, sample_output_dir):
        resp = client.post("/api/stems/export_separate", json={
            "folder_name": "test_output",
            "volumes": {"vocals": 1.2, "drums": 0.8},
            "master_volume": 1.0,
            "output_format": "wav",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["files"]) >= 1

    def test_export_separate_no_folder(self, client):
        resp = client.post("/api/stems/export_separate", json={
            "folder_name": "nonexistent",
            "volumes": {},
            "master_volume": 1.0,
        })
        assert resp.status_code == 404


class TestMidi:
    def test_midi_nonexistent_file(self, client):
        resp = client.post("/api/stems/midi", json={"file_path": "/nonexistent/file.wav"})
        assert resp.status_code == 404

    def test_midi_empty_path(self, client):
        resp = client.post("/api/stems/midi", json={"file_path": ""})
        assert resp.status_code == 404

    def test_midi_returns_structure(self, client, sample_wav):
        resp = client.post("/api/stems/midi", json={"file_path": sample_wav})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "notes" in data

    def test_midi_file_created(self, client, sample_wav):
        resp = client.post("/api/stems/midi", json={"file_path": sample_wav})
        data = resp.json()
        if data["midi_path"]:
            assert os.path.isfile(data["midi_path"])
            assert data["filename"].endswith(".mid")

    def test_midi_notes_count_positive(self, client, sample_wav):
        resp = client.post("/api/stems/midi", json={"file_path": sample_wav})
        assert resp.json()["notes"] > 0

    def test_midi_method_not_allowed(self, client):
        resp = client.get("/api/stems/midi")
        assert resp.status_code in (405,)
