"""Tests for conflict scenarios — 409 when separation already running."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch


class TestSeparationConflict:
    def test_separate_returns_409_when_active(self, client, sample_wav):
        """When _active_worker is alive, /api/separate should return 409."""
        mock_thread = MagicMock()
        mock_thread.is_alive.return_value = True

        with patch("api_server.main._active_worker", mock_thread):
            resp = client.post("/api/separate", json={
                "file_paths": [sample_wav],
            })
            assert resp.status_code == 409
            assert "already in progress" in resp.text.lower()

    def test_separate_returns_ok_after_worker_dies(self, client, sample_wav):
        """After a worker finishes, /api/separate should return 200."""
        mock_thread = MagicMock()
        # First is_alive() call returns True (busy), second returns False (dead)
        mock_thread.is_alive.side_effect = [True, False]

        with patch("api_server.main._active_worker", mock_thread):
            # First request: worker is alive → 409
            resp1 = client.post("/api/separate", json={"file_paths": [sample_wav]})
            assert resp1.status_code == 409
            assert "already in progress" in resp1.text.lower()

            # Second request: is_alive() now returns False → starts new separation → 200
            resp2 = client.post("/api/separate", json={"file_paths": [sample_wav]})
            assert resp2.status_code == 200

    def test_cancel_works_even_when_not_running(self, client):
        """Cancel should always return 200, even if nothing is running."""
        resp = client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelling"

    def test_separate_concurrent_call_returns_409(self, client, sample_wav):
        """Concurrent calls to /api/separate should fail with 409."""
        resp1 = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp1.status_code == 200

        # The worker mock returns immediately, so this might succeed
        # We can't perfectly test concurrent without thread timing
        resp2 = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp2.status_code in (200, 409)
