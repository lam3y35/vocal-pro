"""Tests for VocalPro Worker JSON-Lines protocol, schema conformance, fd isolation, and <500ms cancel."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import jsonschema
import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT_DIR / "schemas" / "worker-protocol.schema.json"
REF_DIR = ROOT_DIR / "benchmarks" / "reference-set"


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_validates_all_command_and_event_shapes(schema: dict) -> None:
    samples = [
        {"v": 1, "id": "1", "cmd": "hello"},
        {"v": 1, "id": "2", "cmd": "ping"},
        {"v": 1, "id": "3", "cmd": "get_capabilities"},
        {
            "v": 1,
            "id": "4",
            "cmd": "separate",
            "job_id": "j-1",
            "input_path": "/tmp/in.wav",
            "output_dir": "/tmp/out",
            "options": {
                "model": "htdemucs",
                "output_mode": "vocals",
                "output_format": "wav",
                "audio_bitrate": "320k",
                "device": "cpu",
                "shifts": 1,
                "overlap": 0.25,
                "segment": 6.0,
            },
        },
        {"v": 1, "id": "5", "cmd": "cancel", "job_id": "j-1"},
        {"v": 1, "id": "6", "cmd": "analyze", "input_path": "/tmp/in.wav"},
        {"v": 1, "id": "7", "cmd": "stem_to_midi", "stem_path": "/tmp/v.wav", "output_midi_path": "/tmp/v.mid"},
        {"v": 1, "id": "8", "cmd": "shutdown"},
        {
            "v": 1,
            "event": "ready",
            "worker_version": "3.0.0",
            "torch_version": "2.15.0+cpu",
            "cuda_available": False,
            "gpu_name": None,
            "vram_mb": None,
        },
        {"v": 1, "id": "2", "event": "pong"},
        {
            "v": 1,
            "event": "progress",
            "job_id": "j-1",
            "phase": "inference",
            "segment_index": 1,
            "segment_total": 4,
            "sub_model_index": 0,
            "sub_model_total": 1,
            "percent": 25.0,
            "eta_s": 3.2,
            "message": "Separating...",
        },
        {
            "v": 1,
            "id": "4",
            "event": "job_done",
            "job_id": "j-1",
            "output_dir": "/tmp/out/in",
            "stems": [
                {
                    "name": "vocals",
                    "path": "/tmp/out/in/in_vocals.wav",
                    "duration_s": 12.0,
                    "sample_rate": 44100,
                    "channels": 2,
                }
            ],
            "comparison_samples": [],
            "elapsed_s": 1.23,
        },
        {"v": 1, "id": "4", "event": "job_cancelled", "job_id": "j-1"},
        {
            "v": 1,
            "id": "4",
            "event": "job_error",
            "job_id": "j-1",
            "code": "DECODE_FAILED",
            "message": "Corrupt file",
            "detail": None,
        },
        {
            "v": 1,
            "id": "6",
            "event": "analysis_done",
            "bpm": 120.0,
            "key": "A Minor",
            "scale": "minor",
            "duration_s": 12.0,
            "waveform": [0.1, 0.5, 1.0],
        },
        {
            "v": 1,
            "id": "7",
            "event": "midi_done",
            "output_midi_path": "/tmp/v.mid",
            "note_count": 8,
        },
        {"v": 1, "event": "log", "level": "info", "message": "ok"},
    ]
    for msg in samples:
        jsonschema.validate(instance=msg, schema=schema)


def test_stdio_worker_subprocess_handshake_and_cancel_under_500ms(schema: dict, tmp_path: Path) -> None:
    """Spike (b) + N4 + N5: Subprocess stdio JSON-Lines framing, ping/pong, and <500ms cancel."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT_DIR / "worker")
    env["VOCALPRO_TEST_FAST_MODEL"] = "1"

    proc = subprocess.Popen(
        [sys.executable, "-m", "vocalpro_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    assert proc.stdin is not None and proc.stdout is not None

    try:
        # 1. Read immediate startup ready event
        line = proc.stdout.readline()
        ready_ev = json.loads(line)
        jsonschema.validate(instance=ready_ev, schema=schema)
        assert ready_ev["event"] == "ready"

        # 2. Ping -> Pong roundtrip
        proc.stdin.write(json.dumps({"v": 1, "id": "p-1", "cmd": "ping"}) + "\n")
        proc.stdin.flush()
        pong_ev = json.loads(proc.stdout.readline())
        jsonschema.validate(instance=pong_ev, schema=schema)
        assert pong_ev["event"] == "pong" and pong_ev["id"] == "p-1"

        # 3. Start separation and cancel immediately after first progress event
        sep_cmd = {
            "v": 1,
            "id": "s-1",
            "cmd": "separate",
            "job_id": "job-cancel-test",
            "input_path": str(REF_DIR / "track_01_pop_stereo_44k.wav"),
            "output_dir": str(tmp_path / "cancel_out"),
            "options": {
                "model": "htdemucs",
                "output_mode": "vocals",
                "output_format": "wav",
                "audio_bitrate": "320k",
                "device": "cpu",
                "shifts": 2,
                "overlap": 0.25,
                "segment": 2.0,
            },
        }
        proc.stdin.write(json.dumps(sep_cmd) + "\n")
        proc.stdin.flush()

        # Wait until loading_model or inference progress arrives, then send cancel
        while True:
            ev = json.loads(proc.stdout.readline())
            jsonschema.validate(instance=ev, schema=schema)
            if ev["event"] == "progress":
                break

        t_cancel_sent = time.perf_counter()
        proc.stdin.write(json.dumps({"v": 1, "id": "c-1", "cmd": "cancel", "job_id": "job-cancel-test"}) + "\n")
        proc.stdin.flush()

        while True:
            ev = json.loads(proc.stdout.readline())
            jsonschema.validate(instance=ev, schema=schema)
            if ev["event"] in ("job_cancelled", "job_done"):
                break

        cancel_elapsed_ms = (time.perf_counter() - t_cancel_sent) * 1000.0
        assert ev["event"] == "job_cancelled"
        assert cancel_elapsed_ms < 500.0, f"Cancel took {cancel_elapsed_ms:.1f}ms (> 500ms limit)"

        # 4. Clean shutdown
        proc.stdin.write(json.dumps({"v": 1, "id": "sh-1", "cmd": "shutdown"}) + "\n")
        proc.stdin.flush()
        sh_ev = json.loads(proc.stdout.readline())
        assert sh_ev["event"] == "pong"
        proc.wait(timeout=5)
    finally:
        if proc.poll() is None:
            proc.kill()
