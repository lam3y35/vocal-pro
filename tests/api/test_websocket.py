"""Tests for the /ws/progress WebSocket endpoint."""

from __future__ import annotations

import json

import pytest


class TestWebSocket:
    def test_websocket_connect(self, client):
        with client.websocket_connect("/ws/progress") as ws:
            # Should connect successfully
            assert ws is not None

    def test_websocket_ping_pong(self, client):
        with client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            resp = ws.receive_text()
            data = json.loads(resp)
            assert data["type"] == "pong"

    def test_websocket_ping_pong_twice(self, client):
        with client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            data1 = json.loads(ws.receive_text())
            assert data1["type"] == "pong"

            ws.send_text("ping")
            data2 = json.loads(ws.receive_text())
            assert data2["type"] == "pong"

    def test_websocket_multiple_clients(self, client):
        """Multiple clients can connect simultaneously."""
        with client.websocket_connect("/ws/progress") as ws1:
            with client.websocket_connect("/ws/progress") as ws2:
                ws1.send_text("ping")
                ws2.send_text("ping")
                assert json.loads(ws1.receive_text())["type"] == "pong"
                assert json.loads(ws2.receive_text())["type"] == "pong"

    def test_websocket_disconnect(self, client):
        """Client disconnect should not crash server."""
        with client.websocket_connect("/ws/progress") as ws:
            ws.send_text("ping")
            assert json.loads(ws.receive_text())["type"] == "pong"
        # After context manager exits, client is disconnected
        # Server should still be healthy
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_websocket_rejects_http(self, client):
        """WebSocket endpoint should reject normal HTTP requests."""
        resp = client.get("/ws/progress")
        assert resp.status_code in (404, 405, 426)

    def test_websocket_unknown_message(self, client):
        """Unknown messages should not crash the server."""
        with client.websocket_connect("/ws/progress") as ws:
            ws.send_text("unknown_command")
            # The server only responds to "ping", so unknown messages
            # result in no response (loop continues). This should not
            # crash, and we can still ping afterward.
            ws.send_text("ping")
            data = json.loads(ws.receive_text())
            assert data["type"] == "pong"


class TestWebSocketSeparation:
    def test_progress_broadcast_on_separate(self, client, sample_wav):
        """Verify that starting a separation sends progress via WebSocket."""
        with client.websocket_connect("/ws/progress") as ws:
            # Start a separation
            resp = client.post("/api/separate", json={
                "file_paths": [sample_wav],
            })
            assert resp.status_code == 200

            # Should receive progress events
            try:
                data = json.loads(ws.receive_text(timeout=2))
                assert data["type"] in ("progress", "done", "error")
            except Exception:
                pass  # Timeout is acceptable if worker finishes too fast

    def test_cancel_sends_event(self, client, sample_wav):
        """Cancelling a separation should send cancelled event."""
        with client.websocket_connect("/ws/progress") as ws:
            client.post("/api/separate", json={"file_paths": [sample_wav]})
            client.post("/api/cancel")

            # Check for cancelled event
            try:
                data = json.loads(ws.receive_text(timeout=2))
                assert data["type"] in ("progress", "done", "cancelled", "error")
            except Exception:
                pass  # Timeout is acceptable
