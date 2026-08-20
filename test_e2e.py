"""End-to-end test: starts the API server, uploads a WAV, runs separation,
and verifies stems are produced. All 10 checks must pass."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
import numpy as np
import soundfile as sf

PROJECT_DIR = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_DIR / "venv" / "Scripts" / "python.exe"
SERVER_PORT = 9876
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
TIMEOUT = 120  # max seconds to wait for separation to complete

passed = 0
failed = 0
checks: list[tuple[str, bool]] = []


def check(description: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        checks.append((description, True))
    else:
        failed += 1
        checks.append((description, False))


def make_wav(path: Path, sr: int = 44100, dur: float = 3.0) -> None:
    t = np.linspace(0, dur, int(sr * dur), endpoint=False)
    left = np.sin(2 * np.pi * 440 * t, dtype=np.float32) * 0.3
    right = np.sin(2 * np.pi * 523 * t, dtype=np.float32) * 0.3
    sf.write(str(path), np.column_stack([left, right]), sr)


def main() -> int:
    global passed, failed
    client = httpx.Client(timeout=30)

    # ── Start server ─────────────────────────────────────────────
    log_path = PROJECT_DIR / "test_e2e_server.log"
    proc = subprocess.Popen(
        [
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "api_server.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(SERVER_PORT),
            "--log-level",
            "warning",
        ],
        cwd=str(PROJECT_DIR),
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        try:
            r = client.get(f"{SERVER_URL}/api/health")
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    check("Server started", proc.poll() is None)

    # ── Health ────────────────────────────────────────────────────
    try:
        r = client.get(f"{SERVER_URL}/api/health")
        check("Health check", r.status_code == 200 and r.json().get("status") == "ok")
    except Exception:
        check("Health check", False)

    # ── Config ────────────────────────────────────────────────────
    try:
        r = client.get(f"{SERVER_URL}/api/config")
        check("Config endpoint", r.status_code == 200 and "config" in r.json())
    except Exception:
        check("Config endpoint", False)

    # ── Models ────────────────────────────────────────────────────
    try:
        r = client.get(f"{SERVER_URL}/api/models")
        data = r.json()
        check("Models list", r.status_code == 200 and len(data.get("models", {})) >= 3)
    except Exception:
        check("Models list", False)

    # ── Upload ────────────────────────────────────────────────────
    test_wav = PROJECT_DIR / "test_e2e_input.wav"
    make_wav(test_wav)
    upload_path = ""
    try:
        with open(test_wav, "rb") as f:
            r = client.post(f"{SERVER_URL}/api/upload", files={"file": f})
        data = r.json()
        upload_path = data.get("file_path", "")
        check("Upload", r.status_code == 200 and bool(upload_path))
    except Exception:
        check("Upload", False)

    # ── Start separation ──────────────────────────────────────────
    job_id = ""
    if upload_path:
        try:
            r = client.post(
                f"{SERVER_URL}/api/separate",
                json={
                    "file_paths": [upload_path],  # API expects file_paths, not file_ids
                    "model_name": "mdx_q",
                    "output_format": "wav",
                },
            )
            data = r.json()
            job_id = data.get("job_id", "")
            check("Separation started", r.status_code == 200 and bool(job_id))
        except Exception:
            check("Separation started", False)

    # ── Wait for completion ───────────────────────────────────────
    completed = False
    if job_id:
        deadline = time.time() + TIMEOUT
        while time.time() < deadline:
            try:
                r = client.get(f"{SERVER_URL}/api/jobs/{job_id}")
                status = r.json().get("job", {}).get("status", "")
                if status == "completed":
                    completed = True
                    break
                elif status in ("error", "cancelled"):
                    break
            except Exception:
                pass
            time.sleep(2)
    check("Separation completed", completed)

    # ── Outputs list ──────────────────────────────────────────────
    outputs_ok = False
    try:
        r = client.get(f"{SERVER_URL}/api/outputs")
        data = r.json()
        outputs_ok = r.status_code == 200 and len(data.get("outputs", [])) >= 1
    except Exception:
        pass
    check("Outputs listed", outputs_ok)

    # ── Stems available ───────────────────────────────────────────
    stems_ok = False
    try:
        r = client.get(f"{SERVER_URL}/api/outputs")
        folders = r.json().get("outputs", [])
        if folders:
            folder_name = folders[0].get("name", "")
            r2 = client.get(f"{SERVER_URL}/api/outputs/{folder_name}/stems")
            data = r2.json()
            stems_ok = r2.status_code == 200 and len(data.get("stems", [])) >= 2
    except Exception:
        pass
    check("Stems available", stems_ok)

    # ── History ───────────────────────────────────────────────────
    history_ok = False
    try:
        r = client.get(f"{SERVER_URL}/api/history")
        data = r.json()
        history_ok = r.status_code == 200 and len(data.get("history", [])) >= 0
    except Exception:
        pass
    check("History endpoint", history_ok)

    # ── Cleanup ───────────────────────────────────────────────────
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    if test_wav.exists():
        test_wav.unlink()
    if log_path.exists():
        try:
            log_path.unlink(missing_ok=True)
        except (PermissionError, OSError):
            pass

    # ── Summary ───────────────────────────────────────────────────
    print()
    print("=" * 55)
    for desc, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {desc}")
    print("=" * 55)
    print(f"  {passed} passed, {failed} failed out of {len(checks)} checks")
    print("=" * 55)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
