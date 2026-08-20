"""Tests for multi-job conflict and cancellation scenarios."""

from __future__ import annotations


class TestSeparationConflict:
    def test_separate_with_multiple_jobs(self, client, sample_wav):
        """Multiple concurrent separation jobs should all be accepted (multi-job)."""
        resp1 = client.post("/api/separate", json={
            "file_paths": [sample_wav],
        })
        assert resp1.status_code == 200
        job1_id = resp1.json().get("job_id")
        assert job1_id is not None

        resp2 = client.post("/api/separate", json={
            "file_paths": [sample_wav],
        })
        assert resp2.status_code == 200
        job2_id = resp2.json().get("job_id")
        assert job2_id is not None

        assert job1_id != job2_id  # Different job IDs for concurrent jobs

    def test_separate_returns_job_ids(self, client, sample_wav):
        """After starting a job, verify the response includes job_id."""
        resp1 = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp1.status_code == 200
        assert "job_id" in resp1.json()

        resp2 = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp2.status_code == 200
        assert "job_id" in resp2.json()

    def test_cancel_works_even_when_not_running(self, client):
        """Cancel should always return 200, even if nothing is running."""
        resp = client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("cancelling", "no_active_job")

    def test_cancel_with_active_job(self, client, sample_wav):
        """Cancel should succeed after starting a separation job."""
        resp = client.post("/api/separate", json={"file_paths": [sample_wav]})
        assert resp.status_code == 200

        resp = client.post("/api/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] in ("cancelling", "no_active_job")
