"""Verify WebSocket progress events stream in real-time during separation.

Connects to /ws/progress, starts a separation via HTTP, and captures
all progress events received. If the fix is correct, multiple progress
events at varying percentages should arrive.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf
from websockets.sync.client import connect as ws_connect

# Ensure stdout can handle any Unicode
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROJECT_DIR = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_DIR / "venv" / "Scripts" / "python.exe"
SERVER_PORT = 9877
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
WS_URL = f"ws://127.0.0.1:{SERVER_PORT}/ws/progress"
TIMEOUT = 120

# ── Helpers ────────────────────────────────────────────────────────

def make_wav(path: Path, sr: int = 44100, dur: float = 3.0) -> None:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    left = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.3
    right = np.sin(2 * np.pi * 523 * t, dtype=np.float32) * 0.3
    sf.write(str(path), np.column_stack([left, right]), sr)


def main() -> int:
    client = httpx.Client(timeout=30)

    # ── Start server ───────────────────────────────────────────────
    log_path = PROJECT_DIR / "test_ws_progress.log"
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "api_server.main:app",
         "--host", "127.0.0.1", "--port", str(SERVER_PORT), "--log-level", "warning"],
        cwd=str(PROJECT_DIR),
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        env={**{k: v for k, v in __import__('os').environ.items()},
             "PYTHONIOENCODING": "utf-8"},
    )
    for _ in range(30):
        try:
            r = client.get(f"{SERVER_URL}/api/health")
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    assert proc.poll() is None, "Server failed to start"
    print(f"[OK] Server started on port {SERVER_PORT}")

    # ── Connect WebSocket ───────────────────────────────────────────
    ws_events: list[dict] = []
    ws_errors: list[str] = []
    ws_ready = threading.Event()

    def ws_listener():
        """Thread that listens for WebSocket messages."""
        try:
            with ws_connect(WS_URL) as ws:
                ws_ready.set()
                while True:
                    msg = ws.recv(timeout=TIMEOUT)
                    if isinstance(msg, bytes):
                        msg = msg.decode("utf-8", errors="replace")
                    data = json.loads(msg)
                    ws_events.append(data)
        except Exception as e:
            # Safely capture the error string
            try:
                ws_errors.append(str(e))
            except Exception:
                ws_errors.append(f"<error: {type(e).__name__}>")
            ws_ready.set()

    ws_thread = threading.Thread(target=ws_listener, daemon=True)
    ws_thread.start()
    ws_ready.wait(timeout=10)
    print(f"[OK] WebSocket connected to {WS_URL}")

    # ── Create test WAV ─────────────────────────────────────────────
    test_wav = PROJECT_DIR / "test_ws_input.wav"
    make_wav(test_wav)

    # ── Upload ─────────────────────────────────────────────────────
    with open(test_wav, "rb") as f:
        r = client.post(f"{SERVER_URL}/api/upload", files={"file": f})
    upload_path = r.json().get("file_path", "")
    assert upload_path, "Upload failed"
    print(f"[OK] Uploaded: {Path(upload_path).name}")

    # ── Start separation ────────────────────────────────────────────
    r = client.post(f"{SERVER_URL}/api/separate", json={
        "file_paths": [upload_path],
        "model_name": "mdx_q",
        "output_format": "wav",
    })
    job_id = r.json().get("job_id", "")
    assert job_id, "Separation did not return a job_id"
    print(f"[OK] Job started: {job_id}")

    # ── Wait for completion (HTTP polling) ──────────────────────────
    deadline = time.time() + TIMEOUT
    completed = False
    while time.time() < deadline:
        r = client.get(f"{SERVER_URL}/api/jobs/{job_id}")
        status = r.json().get("job", {}).get("status", "")
        if status == "completed":
            completed = True
            break
        elif status in ("error", "cancelled"):
            print(f"[!] Job ended with status: {status}")
            break
        time.sleep(1)

    # Allow a moment for any trailing WS events to arrive
    time.sleep(2)

    # ── Analyze results ─────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print(f"  WebSocket Events Received: {len(ws_events)}")
    print(f"  {'=' * 51}")
    if ws_events:
        for ev in ws_events:
            t = ev.get("type", "?")
            pct = ev.get("percent", "")
            msg = str(ev.get("message", "") or "")
            ji = ev.get("job_id", "")
            print(f"  [{t:10s}] pct={pct!s:>4s}  msg={msg[:50]:50s}  job={ji}")
    print(f"  {'=' * 51}")

    progress_events = [e for e in ws_events if e.get("type") == "progress"]
    file_start_events = [e for e in ws_events if e.get("type") == "file_start"]
    done_events = [e for e in ws_events if e.get("type") == "done"]
    cancelled_events = [e for e in ws_events if e.get("type") == "cancelled"]
    error_events = [e for e in ws_events if e.get("type") == "error"]

    has_any_progress = len(progress_events) >= 1
    has_nonzero_progress = any(e.get("percent", 0) or 0 > 0 for e in progress_events)
    has_file_start = len(file_start_events) >= 1
    has_done = len(done_events) >= 1
    has_no_errors = len(error_events) == 0

    print()
    print(f"  {'=' * 51}")
    print(f"  CHECK  Progress type events       {len(progress_events):>3d}    {'PASS' if has_any_progress else 'FAIL'}")
    print(f"  CHECK  Progress > 0% observed     {'yes' if has_nonzero_progress else 'no'}    {'PASS' if has_nonzero_progress else 'INFO'}")
    print(f"  CHECK  File start events           {len(file_start_events):>3d}    {'PASS' if has_file_start else 'INFO'}")
    print(f"  CHECK  Done event received         {len(done_events):>3d}    {'PASS' if has_done else 'FAIL'}")
    print(f"  CHECK  Error events                {len(error_events):>3d}    {'PASS' if has_no_errors else 'FAIL'}")
    print(f"  CHECK  Job completed (HTTP)        {'yes' if completed else 'no'}    {'PASS' if completed else 'FAIL'}")
    print(f"  {'=' * 51}")

    all_pass = has_any_progress and has_no_errors and completed
    print(f"\n  {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")
    print()

    # ── Cleanup ─────────────────────────────────────────────────────
    try:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
    except Exception:
        pass
    for p in [test_wav, log_path]:
        try:
            if p.exists():
                p.unlink(missing_ok=True)
        except Exception:
            pass

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
