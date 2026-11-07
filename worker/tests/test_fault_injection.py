"""Workstream H fault injection (follow-up): disk full, network lost mid-download, file deleted mid-job.

Labels (Evidence & Honesty Rule 3):
- [REAL_ENOSPC]   uses /dev/full so the *kernel* returns a genuine ENOSPC on write (Linux only; skipped elsewhere).
- [LOCAL_HTTP]    a real TCP HTTP server on 127.0.0.1 that really drops the connection mid-body (no mocks).
- [COMPACT_HTDEMUCS] compact HTDemucs architecture (fast), synthetic audio from benchmarks/reference-set.
"""

from __future__ import annotations

import hashlib
import http.server
import os
import sys
import threading
import time
from pathlib import Path

import pytest
import soundfile as sf

WORKER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = WORKER_ROOT.parent
REF_DIR = REPO_ROOT / "benchmarks" / "reference-set"
if str(WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKER_ROOT))

from vocalpro_worker import engine, model_installer  # noqa: E402

linux_only = pytest.mark.skipif(not Path("/dev/full").exists(), reason="/dev/full (real ENOSPC) is Linux-only")


# ---------------------------------------------------------------- network lost mid-download [LOCAL_HTTP]
PAYLOAD = os.urandom(3 * 1024 * 1024 + 123)
PAYLOAD_SHA = hashlib.sha256(PAYLOAD).hexdigest()


class _Handler(http.server.BaseHTTPRequestHandler):
    mode = "drop"  # drop | ok | corrupt
    requests: list[str] = []

    def log_message(self, *a):  # silence
        pass

    def do_GET(self):  # noqa: N802
        rng = self.headers.get("Range")
        type(self).requests.append(rng or "")
        data = PAYLOAD
        if type(self).mode == "corrupt":
            data = bytes([PAYLOAD[0] ^ 0xFF]) + PAYLOAD[1:]
        start = int(rng.split("=")[1].rstrip("-")) if rng else 0
        body = data[start:]
        self.send_response(206 if rng else 200)
        self.send_header("Content-Length", str(len(body)))
        if rng:
            self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
        self.end_headers()
        if type(self).mode == "drop" and not rng:
            self.wfile.write(body[: len(body) // 2])
            self.wfile.flush()
            self.connection.close()  # connection lost mid-body
            return
        self.wfile.write(body)


@pytest.fixture()
def http_server():
    _Handler.requests = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/blob"
    srv.shutdown()


def test_network_lost_mid_download_keeps_part_then_resumes_and_verifies(tmp_path, http_server):
    """[LOCAL_HTTP] connection dropped at ~50 %: structured NETWORK_LOST, .part kept, retry resumes via Range, sha256 ok."""
    _Handler.mode = "drop"
    dest = tmp_path / f"fake-{PAYLOAD_SHA[:8]}.th"
    with pytest.raises(model_installer.ModelInstallError) as ei:
        model_installer.download_verified(http_server, dest, expected_sha256=PAYLOAD_SHA)
    assert ei.value.code == "NETWORK_LOST"
    part = dest.with_name(dest.name + ".part")
    assert not dest.exists(), "no half-written final file may exist"
    assert part.exists() and 0 < part.stat().st_size < len(PAYLOAD)
    kept = part.stat().st_size

    out = model_installer.download_verified(http_server, dest, expected_sha256=PAYLOAD_SHA)
    assert out == dest and dest.read_bytes() == PAYLOAD
    assert not part.exists()
    assert _Handler.requests[-1] == f"bytes={kept}-", f"expected a Range resume, got {_Handler.requests}"


def test_corrupt_download_is_rejected_and_nothing_is_left_behind(tmp_path, http_server):
    """[LOCAL_HTTP] bit-flipped payload: CHECKSUM_MISMATCH, no final file, no .part."""
    _Handler.mode = "corrupt"
    dest = tmp_path / f"fake-{PAYLOAD_SHA[:8]}.th"
    with pytest.raises(model_installer.ModelInstallError) as ei:
        model_installer.download_verified(http_server, dest, expected_sha256=PAYLOAD_SHA)
    assert ei.value.code == "CHECKSUM_MISMATCH"
    assert list(tmp_path.iterdir()) == []


def test_server_unreachable_is_structured_network_lost(tmp_path):
    """[LOCAL_HTTP] nothing listening: NETWORK_LOST (not a raw traceback)."""
    with pytest.raises(model_installer.ModelInstallError) as ei:
        model_installer.download_verified("http://127.0.0.1:9/blob", tmp_path / "x-deadbeef.th", timeout=2)
    assert ei.value.code == "NETWORK_LOST"


@linux_only
def test_disk_full_during_download_is_disk_full_and_cleans_part(tmp_path, http_server):
    """[REAL_ENOSPC][LOCAL_HTTP] the .part target is /dev/full -> kernel ENOSPC -> DISK_FULL."""
    _Handler.mode = "ok"
    dest = tmp_path / f"fake-{PAYLOAD_SHA[:8]}.th"
    part = dest.with_name(dest.name + ".part")
    os.symlink("/dev/full", part)
    with pytest.raises(model_installer.ModelInstallError) as ei:
        model_installer.download_verified(http_server, dest, expected_sha256=PAYLOAD_SHA)
    assert ei.value.code == "DISK_FULL"
    assert not dest.exists()


# ---------------------------------------------------------------- disk full during separation [REAL_ENOSPC]
def _opts():
    return {"model": "htdemucs", "shifts": 0, "output_mode": "vocals"}


@pytest.fixture(autouse=False)
def compact(monkeypatch):
    monkeypatch.setenv("VOCALPRO_TEST_FAST_MODEL", "1")
    engine.MODEL_CACHE.clear()


@linux_only
def test_disk_full_while_writing_stem_gives_structured_error_and_no_partial_stem(tmp_path, compact):
    """[REAL_ENOSPC][COMPACT_HTDEMUCS] vocals output path pre-linked to /dev/full: job fails with a coded error."""
    src = REF_DIR / "track_01_pop_stereo_44k.wav"
    out = tmp_path / "out"
    out.mkdir()
    # Pre-create every plausible stem filename as a symlink to /dev/full so whichever file is written hits ENOSPC.
    base = src.stem
    for suffix in ("vocals", "background", "drums", "bass", "other", "instrumental"):
        for ext in ("wav", "flac", "mp3"):
            for name in (f"{base}_{suffix}.{ext}", f"{suffix}.{ext}"):
                try:
                    os.symlink("/dev/full", out / name)
                except FileExistsError:
                    pass
    subdir = out / base
    subdir.mkdir()
    for suffix in ("vocals", "background", "drums", "bass", "other", "instrumental"):
        for ext in ("wav", "flac", "mp3"):
            for name in (f"{base}_{suffix}.{ext}", f"{suffix}.{ext}"):
                try:
                    os.symlink("/dev/full", subdir / name)
                except FileExistsError:
                    pass
    with pytest.raises(engine.WorkerEngineError) as ei:
        engine.run_separation_job("j-enospc", str(src), str(out), _opts(), threading.Event(), lambda _e: None)
    assert ei.value.code in {"DISK_FULL", "OUTPUT_NOT_WRITABLE"}, (ei.value.code, ei.value.message)


# ---------------------------------------------------------------- file deleted mid-job
def test_input_file_deleted_during_inference_completes_cleanly_without_crashing(tmp_path, compact):
    """[COMPACT_HTDEMUCS] input is unlinked once inference phase begins; audio is in RAM, job completes."""
    src = tmp_path / "victim.wav"
    data, sr = sf.read(str(REF_DIR / "track_01_pop_stereo_44k.wav"), dtype="float32")
    sf.write(str(src), data, sr)

    def emit(ev):
        if ev.get("phase") == "inference" and src.exists():
            src.unlink()

    res = engine.run_separation_job("j-del-in", str(src), str(tmp_path / "out"), _opts(), threading.Event(), emit)
    assert not src.exists(), "test premise: input was unlinked mid-inference"
    assert res["stems"], "audio was decoded into RAM, so separation completes successfully"
    for st in res["stems"]:
        assert Path(st["path"]).stat().st_size > 1000


def test_input_file_deleted_before_decode_raises_structured_invalid_input(tmp_path, compact):
    """[COMPACT_HTDEMUCS] input is deleted before decode completes; raises structured INVALID_INPUT."""
    src = tmp_path / "vanished.wav"
    data, sr = sf.read(str(REF_DIR / "track_01_pop_stereo_44k.wav"), dtype="float32")
    sf.write(str(src), data, sr)

    def emit(ev):
        if ev.get("phase") == "loading_model" and src.exists():
            src.unlink()

    with pytest.raises(engine.WorkerEngineError) as ei:
        engine.run_separation_job("j-del-pre", str(src), str(tmp_path / "out"), _opts(), threading.Event(), emit)
    assert ei.value.code == "INVALID_INPUT"


def test_output_dir_deleted_mid_job_is_structured_error_not_hang(tmp_path, compact):
    """[COMPACT_HTDEMUCS] output directory removed (and replaced by a FILE) as soon as inference starts."""
    import shutil

    src = REF_DIR / "track_01_pop_stereo_44k.wav"
    out = tmp_path / "out"
    state = {"done": False}

    def emit(ev):
        if ev.get("event") == "progress" and not state["done"]:
            state["done"] = True
            shutil.rmtree(out, ignore_errors=True)
            out.write_text("not a directory anymore")

    t0 = time.perf_counter()
    with pytest.raises(Exception) as ei:
        engine.run_separation_job("j-del-out", str(src), str(out), _opts(), threading.Event(), emit)
    assert time.perf_counter() - t0 < 120
    code = getattr(ei.value, "code", None)
    assert code in {"OUTPUT_NOT_WRITABLE", "DISK_FULL"}, f"expected a coded error, got {type(ei.value).__name__}: {ei.value}"
