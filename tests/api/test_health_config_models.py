"""Tests for /api/health, /api/config, /api/models endpoints."""

from __future__ import annotations


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "gpu_available" in data
        assert "gpu_name" in data
        assert "gpu_vram" in data

    def test_health_gpu_false(self, client, mock_torch):
        mock_torch.cuda.is_available.return_value = False
        resp = client.get("/api/health")
        data = resp.json()
        assert data["gpu_available"] is False
        assert data["gpu_name"] == ""
        assert data["gpu_vram"] == ""

    def test_health_gpu_true(self, client, mock_torch):
        mock_torch.cuda.is_available.return_value = True
        mock_torch.cuda.get_device_name.return_value = "NVIDIA RTX 4090"
        mock_torch.cuda.get_device_properties.return_value.total_mem = 24 * 1024**3
        resp = client.get("/api/health")
        data = resp.json()
        assert data["gpu_available"] is True
        assert data["gpu_name"] == "NVIDIA RTX 4090"
        assert "24.0" in data["gpu_vram"]

    def test_health_method_not_allowed(self, client):
        resp = client.post("/api/health")
        assert resp.status_code in (405,)


class TestConfig:
    def test_get_config_returns_dict(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert isinstance(data["config"], dict)
        assert len(data["config"]) > 10

    def test_get_config_has_default_keys(self, client):
        resp = client.get("/api/config")
        cfg = resp.json()["config"]
        for key in [
            "model_name", "segment", "overlap", "shifts", "output_format",
            "enable_vocal_gate", "enable_spectral_denoise", "gate_threshold_db",
            "denoise_strength", "min_vocal_duration", "safe_mode", "max_threads",
            "include_sfx", "save_background_track", "trim_silence",
            "enable_sfx_separation",
        ]:
            assert key in cfg, f"Missing config key: {key}"

    def test_update_config_single(self, client):
        resp = client.post("/api/config", json=[{"key": "segment", "value": 16.0}])
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["config"]["segment"] == 16.0

    def test_update_config_multiple(self, client):
        resp = client.post("/api/config", json=[
            {"key": "segment", "value": 8.0},
            {"key": "shifts", "value": 3},
        ])
        assert resp.status_code == 200
        cfg = resp.json()["config"]
        assert cfg["segment"] == 8.0
        assert cfg["shifts"] == 3

    def test_update_config_persists(self, client):
        client.post("/api/config", json=[{"key": "segment", "value": 24.0}])
        resp2 = client.get("/api/config")
        assert resp2.json()["config"]["segment"] == 24.0

    def test_update_config_bool(self, client):
        resp = client.post("/api/config", json=[{"key": "enable_vocal_gate", "value": False}])
        assert resp.json()["config"]["enable_vocal_gate"] is False

    def test_update_config_string(self, client):
        resp = client.post("/api/config", json=[{"key": "model_name", "value": "mdx_extra"}])
        assert resp.json()["config"]["model_name"] == "mdx_extra"

    def test_update_config_empty_list(self, client):
        resp = client.post("/api/config", json=[])
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_update_config_invalid_json(self, client):
        resp = client.post("/api/config", content="not json", headers={"Content-Type": "application/json"})
        assert resp.status_code in (422, 400)


class TestModels:
    def test_list_models_returns_dict(self, client):
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert isinstance(data["models"], dict)

    def test_list_models_has_key_models(self, client):
        resp = client.get("/api/models")
        models = resp.json()["models"]
        for key in ["htdemucs_ft", "htdemucs", "mdx", "mdx_extra"]:
            assert key in models, f"Missing model: {key}"

    def test_htdemucs_ft_is_recommended(self, client):
        models = client.get("/api/models").json()["models"]
        assert models["htdemucs_ft"].get("recommended") is True

    def test_all_models_have_name_and_desc(self, client):
        models = client.get("/api/models").json()["models"]
        for key, val in models.items():
            assert val["name"] == key, f"Model {key} has mismatched name"
            assert "description" in val, f"Model {key} missing description"
            assert len(val["description"]) > 5, f"Model {key} has short description"

    def test_models_count(self, client):
        models = client.get("/api/models").json()["models"]
        assert len(models) >= 7  # At least the standard models

    def test_models_are_immutable(self, client):
        """Verify we can call twice and get same results."""
        m1 = client.get("/api/models").json()["models"]
        m2 = client.get("/api/models").json()["models"]
        assert m1 == m2
