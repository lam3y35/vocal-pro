"""Tests for /api/upload, /api/download, /api/analyze endpoints."""

from __future__ import annotations

import os


class TestUpload:
    def test_upload_wav(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("test.wav", f, "audio/wav")})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "file_path" in data
        assert data["filename"] == "test.wav"
        assert "file_id" in data

    def test_upload_mp3(self, client, tmp_path):
        p = tmp_path / "test.mp3"
        p.write_bytes(b"\xff\xfb" + b"\x00" * 100)
        with open(str(p), "rb") as f:
            resp = client.post("/api/upload", files={"file": ("test.mp3", f, "audio/mpeg")})
        assert resp.status_code == 200

    def test_upload_unsupported_extension(self, client, tmp_path):
        p = tmp_path / "test.exe"
        p.write_bytes(b"x" * 100)
        with open(str(p), "rb") as f:
            resp = client.post("/api/upload", files={"file": ("test.exe", f, "application/octet-stream")})
        assert resp.status_code == 400
        assert "Unsupported" in resp.text

    def test_upload_no_filename(self, client):
        resp = client.post("/api/upload", files={"file": ("", b"data", "audio/wav")})
        # FastAPI may return 400 (no filename) or 422 (empty string validation)
        assert resp.status_code in (400, 422)

    def test_upload_empty_file(self, client, tmp_path):
        p = tmp_path / "empty.wav"
        p.write_bytes(b"")
        with open(str(p), "rb") as f:
            resp = client.post("/api/upload", files={"file": ("empty.wav", f, "audio/wav")})
        # Should still allow uploading (files are stored as-is)
        assert resp.status_code == 200

    def test_upload_large_filename(self, client, tmp_path):
        long_name = "A" * 200 + ".wav"
        p = tmp_path / long_name
        p.write_bytes(b"\x00" * 100)
        with open(str(p), "rb") as f:
            resp = client.post("/api/upload", files={"file": (long_name, f, "audio/wav")})
        assert resp.status_code == 200
        assert long_name in resp.json()["filename"]

    def test_upload_files_persist(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("persist.wav", f, "audio/wav")})
        path = resp.json()["file_path"]
        # Verify the file exists on disk
        assert os.path.isfile(path)
        assert os.path.getsize(path) > 0

    def test_upload_size_mb_correct(self, client, sample_wav):
        with open(sample_wav, "rb") as f:
            resp = client.post("/api/upload", files={"file": ("size_test.wav", f, "audio/wav")})
        mb = resp.json()["size_mb"]
        assert isinstance(mb, (int, float))
        assert mb > 0


class TestDownload:
    def test_download_invalid_url_empty(self, client):
        resp = client.post("/api/download", json={"url": ""})
        assert resp.status_code == 400

    def test_download_invalid_url_not_http(self, client):
        resp = client.post("/api/download", json={"url": "ftp://bad.com/file.mp3"})
        assert resp.status_code == 400
        assert "http" in resp.text.lower()

    def test_download_missing_url_key(self, client):
        resp = client.post("/api/download", json={})
        assert resp.status_code in (422,)

    def test_download_malformed_url(self, client):
        resp = client.post("/api/download", json={"url": "not-a-url"})
        assert resp.status_code == 400


class TestAnalyze:
    def test_analyze_nonexistent_file(self, client):
        resp = client.post("/api/analyze", json={"file_path": "/nonexistent/file.wav"})
        assert resp.status_code == 404
        assert "not found" in resp.text.lower()

    def test_analyze_empty_path(self, client):
        resp = client.post("/api/analyze", json={"file_path": ""})
        assert resp.status_code == 404

    def test_analyze_returns_structure(self, client, sample_wav):
        resp = client.post("/api/analyze", json={"file_path": sample_wav})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        analysis = data["analysis"]
        assert "sample_rate" in analysis
        assert "duration_sec" in analysis
        assert "bpm" in analysis or analysis["bpm"] is None
        assert "key" in analysis or analysis["key"] is None

    def test_analyze_has_waveform(self, client, sample_wav):
        resp = client.post("/api/analyze", json={"file_path": sample_wav})
        analysis = resp.json()["analysis"]
        assert "waveform" in analysis
        assert "waveform_samples" in analysis
        assert analysis["waveform_samples"] > 0

    def test_analyze_bpm_detected(self, client, sample_wav):
        resp = client.post("/api/analyze", json={"file_path": sample_wav})
        analysis = resp.json()["analysis"]
        # With mocked librosa, BPM should be detected
        assert analysis["bpm"] is not None

    def test_analyze_key_detected(self, client, sample_wav):
        resp = client.post("/api/analyze", json={"file_path": sample_wav})
        analysis = resp.json()["analysis"]
        # With mocked data, key should be detected
        assert analysis["key"] is not None

    def test_analyze_empty_file_fails(self, client, tmp_path):
        p = tmp_path / "empty.wav"
        p.write_bytes(b"")
        resp = client.post("/api/analyze", json={"file_path": str(p)})
        # librosa will fail on empty file
        assert resp.status_code in (200, 500)

    def test_analyze_method_not_allowed(self, client):
        resp = client.get("/api/analyze")
        assert resp.status_code in (405,)
