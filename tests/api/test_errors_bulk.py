"""Tests for error handling, CORS, and bulk parametrized scenarios."""

from __future__ import annotations

import pytest


class TestCors:
    def test_cors_headers_present(self, client):
        resp = client.options("/api/health", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        })
        assert resp.status_code == 200
        headers = resp.headers
        # Check CORS headers exist
        assert "access-control-allow-origin" in headers

    def test_cors_allows_all_origins(self, client):
        for origin in ["http://localhost:3000", "http://example.com", "https://app.vocalpro.com"]:
            resp = client.options("/api/health", headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            })
            # With allow_origins=['*'], the middleware may echo back the origin
            # instead of returning literal '*'. Accept both behaviors.
            allow = resp.headers.get("access-control-allow-origin", "")
            assert allow == "*" or allow == origin, f"Got '{allow}', expected '*' or '{origin}'"


class TestErrorHandling:
    def test_404_unknown_route(self, client):
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_405_wrong_method(self, client):
        resp = client.delete("/api/health")
        assert resp.status_code in (405,)

    def test_422_validation_error(self, client):
        # Send invalid type for a field
        resp = client.post("/api/separate", json={"file_paths": "not_a_list"})
        assert resp.status_code in (422,)

    def test_empty_request_body(self, client):
        resp = client.post("/api/separate", data="", headers={"Content-Type": "application/json"})
        assert resp.status_code in (400, 422)

    def test_malformed_json(self, client):
        resp = client.post("/api/separate", data="not json {{{", headers={"Content-Type": "application/json"})
        assert resp.status_code in (400, 422)

    def test_websocket_rejects_http(self, client):
        resp = client.get("/ws/progress")
        # WebSocket endpoint rejects HTTP requests
        assert resp.status_code in (404, 405, 426, 400)


class TestBulkEndpoints:
    """Bulk parametrized tests for all endpoints."""

    @pytest.mark.parametrize("method,path", [
        ("GET", "/api/health"),
        ("GET", "/api/config"),
        ("GET", "/api/models"),
        ("GET", "/api/status"),
        ("GET", "/api/history"),
        ("GET", "/api/download_history"),
        ("GET", "/api/outputs"),
    ])
    def test_get_endpoints_return_200(self, client, method, path):
        resp = client.request(method, path)
        assert resp.status_code == 200, f"{method} {path} returned {resp.status_code}"

    @pytest.mark.parametrize("path", [
        "/api/health",
        "/api/models",
        "/api/status",
        "/api/history",
        "/api/outputs",
    ])
    def test_post_to_get_endpoints(self, client, path):
        """POST to GET-only endpoints should fail.
        Note: /api/config is excluded because POST is a valid method for config updates."""
        resp = client.post(path)
        assert resp.status_code in (405, 404)

    @pytest.mark.parametrize("path", [
        "/api/history",
        "/api/download_history",
    ])
    def test_delete_endpoints(self, client, path):
        resp = client.delete(path)
        assert resp.status_code == 200

    @pytest.mark.parametrize("body", [
        {"file_paths": []},
        {"file_paths": ["/nonexistent1", "/nonexistent2"]},
        {},
        {"file_paths": None},
    ])
    def test_separate_invalid_bodies(self, client, body):
        resp = client.post("/api/separate", json=body)
        assert resp.status_code in (400, 422)

    @pytest.mark.parametrize("url", [
        "",
        "not-a-url",
        "ftp://bad.com/file.mp3",
    ])
    def test_download_invalid_urls(self, client, url):
        """URLs that fail validation should return 400/422.
        Note: http:// and https:// pass URL validation but fail at fetch (500)."""
        resp = client.post("/api/download", json={"url": url})
        assert resp.status_code in (400, 422)

    @pytest.mark.parametrize("fmt", ["wav", "mp3", "flac"])
    def test_output_format_accepted(self, client, sample_wav, fmt):
        resp = client.post("/api/separate", json={
            "file_paths": [sample_wav],
            "output_format": fmt,
        })
        assert resp.status_code == 200

    @pytest.mark.parametrize("model", [
        "htdemucs_ft", "htdemucs", "mdx", "mdx_extra",
    ])
    def test_valid_models_in_separation(self, client, sample_wav, model):
        resp = client.post("/api/separate", json={
            "file_paths": [sample_wav],
            "model_name": model,
        })
        assert resp.status_code == 200

    @pytest.mark.parametrize("vol", [0.0, 0.5, 1.0, 2.0])
    def test_preview_volumes(self, client, sample_output_dir, vol):
        resp = client.post("/api/stems/preview", json={
            "folder_name": "test_output",
            "volumes": {"vocals": vol},
            "master_volume": 1.0,
        })
        assert resp.status_code in (200, 400)
