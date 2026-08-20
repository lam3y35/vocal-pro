"""VocalPro – FastAPI backend server.

Provides REST + WebSocket endpoints for the Flutter frontend to:
  • Upload audio/video files
  • Configure and start separation (multiple concurrent jobs)
  • Stream real-time progress via WebSocket (per-job)
  • Browse output files and stem mixer
  • Manage download/separation history
"""

from __future__ import annotations

import asyncio
import gc
import json
import logging
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from contextlib import asynccontextmanager

# ── Project path setup (keep before project imports) ──────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ── Project & third-party imports (E402: sys.path modified just above) ─
from code.config import DEFAULT_CONFIG, load_config, save_config  # noqa: E402
from code._shared import _DATA_DIR, _HISTORY_FILE, _SEP_HISTORY_FILE, _SUPPORTED_EXTS  # noqa: E402

from fastapi import FastAPI, Body, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

# librosa, numpy, soundfile are lazy-imported inside the endpoints that need
# them (analyze, stems, preview). This avoids ~2-3s startup penalty from
# loading the heavy audio/ML stack at import time.
np = None  # type: ignore
sf = None  # type: ignore


logger = logging.getLogger("vocalpro.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# ── Server lifecycle (lifespan) ────────────────────────────────────


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Capture the main event loop at startup for thread-safe WebSocket broadcasts."""
    global _MAIN_LOOP  # noqa
    _MAIN_LOOP = asyncio.get_running_loop()
    logger.info("Main event loop captured for thread-safe WebSocket sends")
    yield
    # No cleanup needed on shutdown


# ── App state ─────────────────────────────────────────────────────────
app = FastAPI(title="VocalPro API", version="1.0.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
UPLOAD_DIR = os.path.join(_DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Default output directory
OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output_vocals")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Multi-job system ───────────────────────────────────────────────────
# Each concurrent separation gets a unique job_id. Jobs are stored in
# _jobs and managed via /api/separate (create), /api/jobs (list),
# /api/jobs/{job_id} (detail), /api/jobs/{job_id}/cancel (cancel).
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()
_next_job_num = 0  # Monotonic job number for friendly display names

# WebSocket connections for real-time progress
_progress_connections: list[WebSocket] = []
_progress_lock = threading.Lock()

# Auto-cleanup: remove completed jobs older than this (seconds)
_JOB_CLEANUP_AGE = 300  # 5 minutes
_LAST_CLEANUP = time.time()

# Main event loop reference for thread-safe WebSocket sends from worker threads.
# Captured at server startup by the _lifespan lifecycle handler.
_MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None  # noqa: F824 — assigned via 'global' in _lifespan()


# ── Job helpers ────────────────────────────────────────────────────────

def _create_job(file_paths: list[str], config: dict) -> str:
    """Create a new job record and return its job_id."""
    global _next_job_num
    with _jobs_lock:
        _next_job_num += 1
        job_id = f"job_{_next_job_num}"
        now = time.time()
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "cancel_event": threading.Event(),
            "worker": None,
            "files": list(file_paths),
            "progress": {},        # file_index -> float (0-1) or str ('done'/'error'/'cancelled')
            "output_paths": {},    # file_index -> output_path
            "total_progress": 0.0,
            "status_text": "Queued",
            "current_file": -1,
            "total_files": len(file_paths),
            "current_filename": None,
            "error": None,
            "config": dict(config),  # snapshot of config used
            "created_at": now,
            "completed_at": None,
        }
    return job_id


def _update_job(job_id: str, **kwargs):
    """Update fields on a job in a thread-safe manner."""
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _get_job(job_id: str) -> Optional[dict]:
    """Get a snapshot of a job."""
    with _jobs_lock:
        return dict(_jobs.get(job_id, {}))


def _list_jobs() -> list[dict]:
    """Return a list of all job snapshots (excluding cancel_event/worker)."""
    with _jobs_lock:
        results = []
        for jid, job in _jobs.items():
            entry = dict(job)
            entry.pop("cancel_event", None)
            entry.pop("worker", None)
            results.append(entry)
        return results


def _cleanup_old_jobs():
    """Remove completed/cancelled jobs older than _JOB_CLEANUP_AGE."""
    global _LAST_CLEANUP
    now = time.time()
    if now - _LAST_CLEANUP < 60:
        return  # Only run once per minute
    _LAST_CLEANUP = now
    cutoff = now - _JOB_CLEANUP_AGE
    with _jobs_lock:
        dead = []
        for jid, job in _jobs.items():
            if job["status"] in ("completed", "error", "cancelled"):
                completed = job.get("completed_at") or job.get("created_at", 0)
                if completed < cutoff:
                    dead.append(jid)
        for jid in dead:
            del _jobs[jid]
        if dead:
            logger.info("Cleaned up %d old job(s)", len(dead))


def _broadcast(msg: dict):
    """Send progress to all connected WebSocket clients (thread-safe).

    Called from background worker threads during separation. Uses the
    main thread's captured event loop via run_coroutine_threadsafe to
    send messages across threads safely.

    If the main loop hasn't been captured yet (early startup), or if a
    client disconnected between iterations, errors are caught and the
    problematic connection is removed.
    """
    global _MAIN_LOOP
    data = json.dumps(msg)
    dead: list[WebSocket] = []
    with _progress_lock:
        targets = list(_progress_connections)

    # _MAIN_LOOP is captured by the lifespan handler before any requests
    # are accepted, so it's always populated by the time a separation runs.
    # If it's somehow None (very early startup), skip the broadcast.
    loop = _MAIN_LOOP
    if loop is None or not loop.is_running():
        return

    for ws in targets:
        try:
            asyncio.run_coroutine_threadsafe(ws.send_text(data), loop)
        except Exception:
            dead.append(ws)
    if dead:
        with _progress_lock:
            for ws in dead:
                try:
                    _progress_connections.remove(ws)
                except ValueError:
                    pass


def _broadcast_job(job_id: str, msg: dict):
    """Broadcast a message with job_id attached."""
    msg["job_id"] = job_id
    _broadcast(msg)


def _start_worker(
    job_id: str,
    valid_files: list[str],
    output_dir: str,
    base_engine_config: dict,
):
    """Start a worker thread for a job."""

    def _worker():
        job_snapshot = _get_job(job_id)
        cancel_event = job_snapshot.get("cancel_event") if job_snapshot else None
        if cancel_event is None:
            return

        try:
            import torch
            from code.separation_engine import SeparationEngine

            _update_job(job_id, status="running", status_text="Initializing...")
            _broadcast_job(job_id, {
                "type": "progress", "percent": 0,
                "message": "Initializing...",
            })

            pw = max(1, min(4, base_engine_config.get("parallel_workers", 1)))
            total = len(valid_files)

            _broadcast_job(job_id, {
                "type": "progress", "percent": 0,
                "message": f"Starting {pw} worker(s) for {total} file(s)...",
            })

            results: dict[int, str] = {}
            file_futures = {}

            with ThreadPoolExecutor(max_workers=pw) as pool:
                def _run_one(file_path: str, file_index: int) -> tuple[int, str]:
                    try:
                        def _progress_cb(pct: float, msg: str):
                            # Broadcast progress via WebSocket
                            _broadcast_job(job_id, {
                                "type": "progress",
                                "percent": pct,
                                "message": msg,
                                "file_index": file_index,
                            })
                            # Also update the job record so HTTP polling sees real progress
                            _update_job(job_id, total_progress=pct / 100.0, status_text=msg)

                        engine = SeparationEngine(
                            dict(base_engine_config),
                            progress_callback=_progress_cb,
                            cancel_event=cancel_event,
                        )

                        _broadcast_job(job_id, {
                            "type": "file_start",
                            "index": file_index,
                            "total": total,
                            "filename": os.path.basename(file_path),
                        })

                        out = engine.separate_file(file_path, output_dir)

                        del engine
                        gc.collect()
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()

                        return (file_index, out)

                    except InterruptedError:
                        return (file_index, "")
                    except Exception as e:
                        _broadcast_job(job_id, {
                            "type": "error",
                            "message": f"[{os.path.basename(file_path)}] {e}",
                            "file_index": file_index,
                        })
                        return (file_index, "")

                for i, file_path in enumerate(valid_files):
                    if cancel_event.is_set():
                        break
                    future = pool.submit(_run_one, file_path, i)
                    file_futures[future] = i

                for future in as_completed(file_futures):
                    if cancel_event.is_set():
                        try:
                            pool.shutdown(wait=False, cancel_futures=True)
                        except Exception:
                            pass
                        break
                    try:
                        idx, out_path = future.result()
                        results[idx] = out_path
                    except InterruptedError:
                        cancel_event.set()
                        try:
                            pool.shutdown(wait=False, cancel_futures=True)
                        except Exception:
                            pass
                        break
                    except Exception as e:
                        _broadcast_job(job_id, {
                            "type": "error",
                            "message": f"Worker error: {e}",
                        })

            if cancel_event.is_set():
                _update_job(job_id, status="cancelled", status_text="Cancelled", total_progress=0.0, completed_at=time.time())
                _broadcast_job(job_id, {"type": "cancelled"})
            else:
                last_output = None
                for idx in sorted(results.keys()):
                    if results[idx]:
                        last_output = results[idx]
                _update_job(job_id, status="completed", status_text="Complete", total_progress=1.0, completed_at=time.time())
                _broadcast_job(job_id, {"type": "done", "output_path": last_output})

        except Exception as e:
            import traceback
            traceback.print_exc()
            _update_job(job_id, status="error", error=str(e), status_text="Error", total_progress=0.0, completed_at=time.time())
            _broadcast_job(job_id, {"type": "error", "message": str(e)})

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    _update_job(job_id, worker=worker)


# ── Pydantic models ──────────────────────────────────────────────────

class SeparationRequest(BaseModel):
    file_paths: list[str]
    output_dir: Optional[str] = None
    model_name: str = "htdemucs"
    output_format: str = "wav"
    # Processing options
    enable_vocal_gate: bool = True
    enable_spectral_denoise: bool = True
    enable_multiband_denoise: bool = False
    enable_noise_profile: bool = False
    adaptive_gate_floor: bool = False
    trim_silence: bool = False
    karaoke_mode: bool = False
    ensemble_mode: bool = False
    include_sfx: bool = True
    save_background_track: bool = False
    generate_comparison_samples: bool = False
    enable_sfx_separation: bool = False
    # Advanced
    segment: float = 6.0
    overlap: float = 2.0
    shifts: int = 1
    gate_threshold_db: float = -55.0
    gate_floor_db: float = -60.0
    denoise_strength: float = 0.55
    min_vocal_duration: float = 0.08
    video_output_mode: str = "both"
    parallel_workers: int = 1


class ConfigUpdate(BaseModel):
    key: str
    value: Any


class DownloadRequest(BaseModel):
    url: str


# ── REST Endpoints ────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    import torch
    gpu_available = torch.cuda.is_available()
    gpu_name = ""
    gpu_vram = ""
    if gpu_available:
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_mem / (1024 ** 3)
        gpu_vram = f"{vram:.1f} GB"
    return {
        "status": "ok",
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "gpu_vram": gpu_vram,
    }


@app.get("/api/config")
async def get_config():
    """Return current configuration."""
    cfg = load_config()
    return {"config": cfg}


@app.get("/api/config/defaults")
async def get_defaults():
    """Return DEFAULT_CONFIG — factory defaults for every setting."""
    return {"defaults": dict(DEFAULT_CONFIG)}


@app.post("/api/config")
async def update_config(updates: list[ConfigUpdate]):
    """Update configuration values."""
    cfg = load_config()
    for update in updates:
        cfg[update.key] = update.value
    save_config(cfg)
    return {"status": "ok", "config": cfg}


@app.get("/api/models")
async def list_models():
    """Return available AI models with descriptions."""
    models = {
        "htdemucs_ft": {"name": "htdemucs_ft", "description": "Best quality — fine-tuned (recommended, ~3.5 GB VRAM)", "recommended": True},
        "htdemucs": {"name": "htdemucs", "description": "Faster — base transformer, slightly lower quality"},
        "htdemucs_6s": {"name": "htdemucs_6s", "description": "6-stem — isolates piano + guitar as separate tracks"},
        "hdemucs_mmi": {"name": "hdemucs_mmi", "description": "v3 architecture — different separation profile"},
        "mdx": {"name": "mdx", "description": "MDX winner — good balance of speed & quality"},
        "mdx_extra": {"name": "mdx_extra", "description": "MDX extra — more robust with extra training data"},
        "mdx_q": {"name": "mdx_q", "description": "MDX quantized — smaller, very fast, lower quality"},
        "mdx_extra_q": {"name": "mdx_extra_q", "description": "MDX extra quantized — good for low VRAM systems"},
    }
    return {"models": models}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload an audio/video file for processing."""
    if not file.filename:
        raise HTTPException(400, "No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in _SUPPORTED_EXTS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Supported: {', '.join(_SUPPORTED_EXTS)}")

    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{file.filename}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)

    size_mb = os.path.getsize(save_path) / (1024 * 1024)
    return {
        "status": "ok",
        "file_path": save_path,
        "filename": file.filename,
        "file_id": file_id,
        "size_mb": round(size_mb, 2),
    }


@app.post("/api/download")
async def download_url(req: DownloadRequest):
    """Download a file from a URL."""
    import urllib.request
    from urllib.parse import urlparse

    url = req.url
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    name = "downloaded_file"
    try:
        parsed = urlparse(url)
        name = os.path.basename(parsed.path) or name
    except Exception:
        pass

    if "." not in name:
        name += ".mp3"

    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{name}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    try:
        urllib.request.urlretrieve(url, save_path)
    except Exception as e:
        raise HTTPException(500, f"Download failed: {e}")

    size_mb = os.path.getsize(save_path) / (1024 * 1024)
    return {
        "status": "ok",
        "file_path": save_path,
        "filename": name,
        "file_id": file_id,
        "size_mb": round(size_mb, 2),
    }


# ── Multi-job separation endpoints ─────────────────────────────────────

@app.post("/api/separate")
async def start_separation(req: SeparationRequest):
    """Start audio separation in background with a new job. Progress via WebSocket."""
    _cleanup_old_jobs()

    valid_files = [f for f in req.file_paths if os.path.isfile(f)]
    if not valid_files:
        raise HTTPException(400, "No valid files provided")

    output_dir = req.output_dir or OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    base_engine_config = {
        "model_name": req.model_name,
        "segment": req.segment,
        "overlap": req.overlap,
        "shifts": req.shifts,
        "output_format": req.output_format,
        "include_sfx": req.include_sfx,
        "save_background_track": req.save_background_track,
        "generate_comparison_samples": req.generate_comparison_samples,
        "trim_silence": req.trim_silence,
        "enable_vocal_gate": req.enable_vocal_gate,
        "enable_spectral_denoise": req.enable_spectral_denoise,
        "enable_multiband_denoise": req.enable_multiband_denoise,
        "enable_noise_profile": req.enable_noise_profile,
        "adaptive_gate_floor": req.adaptive_gate_floor,
        "enable_sfx_separation": req.enable_sfx_separation,
        "karaoke_mode": req.karaoke_mode,
        "ensemble_mode": req.ensemble_mode,
        "gate_threshold_db": req.gate_threshold_db,
        "gate_floor_db": req.gate_floor_db,
        "denoise_strength": req.denoise_strength,
        "min_vocal_duration": req.min_vocal_duration,
        "video_output_mode": req.video_output_mode,
        "parallel_workers": req.parallel_workers,
        "device": "auto",
    }

    job_id = _create_job(valid_files, base_engine_config)
    # Inject job_id into engine config for progress estimation subprocess
    base_engine_config["_job_id"] = job_id
    _start_worker(job_id, valid_files, output_dir, base_engine_config)

    return {
        "status": "started",
        "job_id": job_id,
        "file_count": len(valid_files),
        "output_dir": output_dir,
    }


@app.get("/api/jobs")
async def list_jobs():
    """List all jobs (active and recent completed)."""
    _cleanup_old_jobs()
    jobs = _list_jobs()
    return {"jobs": jobs}


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """Get details of a specific job."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    job.pop("cancel_event", None)
    job.pop("worker", None)
    return {"job": job}


@app.post("/api/jobs/{job_id}/progress")
async def update_job_progress(job_id: str, percent: float = Body(0.0), message: str = Body("")):
    """External progress update endpoint (used by estimation subprocess).
    
    The subprocess sends percent and message as a JSON body. Using Body()
    ensures FastAPI reads them from the request body rather than treating
    them as query parameters.
    """
    _update_job(job_id, total_progress=percent / 100.0, status_text=message)
    return {"status": "ok"}


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a specific job."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    cancel_event = None
    with _jobs_lock:
        if job_id in _jobs:
            cancel_event = _jobs[job_id].get("cancel_event")
    if cancel_event:
        cancel_event.set()
        _update_job(job_id, status="cancelled", status_text="Cancelling...")
    return {"status": "cancelling", "job_id": job_id}


@app.post("/api/cancel")
async def cancel_separation():
    """Cancel the most recent running job (backward-compatible)."""
    with _jobs_lock:
        # Find the most recent running job
        running = []
        for jid, job in _jobs.items():
            if job["status"] == "running":
                ce = job.get("cancel_event")
                running.append((job.get("created_at", 0), jid, ce))
    if running:
        running.sort(reverse=True)
        _, jid, ce = running[0]
        if ce:
            ce.set()
            _update_job(jid, status="cancelled", status_text="Cancelling...")
            return {"status": "cancelling", "job_id": jid}
    return {"status": "no_active_job"}


@app.get("/api/status")
async def get_status():
    """Get current processing status (checks if any job is running)."""
    _cleanup_old_jobs()
    running_jobs = []
    with _jobs_lock:
        for jid, job in _jobs.items():
            if job["status"] == "running":
                w = job.get("worker")
                running_jobs.append({
                    "job_id": jid,
                    "status": "running",
                    "alive": w is not None and w.is_alive(),
                })
    return {
        "is_running": len(running_jobs) > 0,
        "running_jobs": running_jobs,
    }


# ── History ────────────────────────────────────────────────────────────

@app.get("/api/history")
async def get_history():
    """Return separation history."""
    history = []
    try:
        if os.path.isfile(_SEP_HISTORY_FILE):
            with open(_SEP_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
    except Exception:
        pass
    return {"history": history}


@app.get("/api/download_history")
async def get_download_history():
    """Return download history."""
    history = []
    try:
        if os.path.isfile(_HISTORY_FILE):
            with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
    except Exception:
        pass
    return {"history": history}


@app.delete("/api/history")
async def clear_sep_history():
    """Clear separation history."""
    try:
        if os.path.isfile(_SEP_HISTORY_FILE):
            with open(_SEP_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
    except Exception as e:
        raise HTTPException(500, f"Failed to clear history: {e}")
    return {"status": "ok"}


@app.delete("/api/download_history")
async def clear_download_history():
    """Clear download history."""
    try:
        if os.path.isfile(_HISTORY_FILE):
            with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f)
    except Exception as e:
        raise HTTPException(500, f"Failed to clear history: {e}")
    return {"status": "ok"}


@app.post("/api/rerun")
async def rerun_separation(req: SeparationRequest):
    """Re-run separation (alias for /api/separate)."""
    return await start_separation(req)


# ── Outputs ────────────────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs():
    """List output directories and their stem files."""
    results = []
    if not os.path.isdir(OUTPUT_DIR):
        return {"outputs": results}

    for entry in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        entry_path = os.path.join(OUTPUT_DIR, entry)
        if os.path.isdir(entry_path):
            files = []
            for f in os.listdir(entry_path):
                fp = os.path.join(entry_path, f)
                if os.path.isfile(fp):
                    files.append({
                        "name": f,
                        "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 2),
                        "path": fp,
                    })
            results.append({"name": entry, "path": entry_path, "files": files})

    return {"outputs": results}


@app.get("/api/outputs/{folder_name}/stems")
async def get_stems(folder_name: str):
    """List stem files in an output folder."""
    folder_path = os.path.join(OUTPUT_DIR, folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(404, "Folder not found")

    stem_suffixes = {
        "vocals": "Vocals", "drums": "Drums", "bass": "Bass",
        "other": "Other", "guitar": "Guitar", "piano": "Piano",
    }
    stems = []
    for f in sorted(os.listdir(folder_path)):
        f_lower = f.lower()
        for suffix, label in stem_suffixes.items():
            if suffix in f_lower and f.endswith((".wav", ".mp3", ".flac")):
                fp = os.path.join(folder_path, f)
                stems.append({
                    "key": suffix,
                    "label": label,
                    "filename": f,
                    "path": fp,
                    "size_mb": round(os.path.getsize(fp) / (1024 * 1024), 2),
                })
                break

    return {"stems": stems}


@app.get("/api/outputs/{folder_name}/{file_name}")
async def get_output_file(folder_name: str, file_name: str):
    """Download a specific output file."""
    file_path = os.path.join(OUTPUT_DIR, folder_name, file_name)
    if not os.path.isfile(file_path):
        raise HTTPException(404, "File not found")
    return FileResponse(file_path, filename=file_name)


# ── Audio Analysis ────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    file_path: str

@app.post("/api/analyze")
async def analyze_audio(req: AnalyzeRequest):
    """Analyze audio file: BPM, musical key, and waveform data (downsampled)."""
    file_path = req.file_path
    if not os.path.isfile(file_path):
        raise HTTPException(404, "File not found")

    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.webm', '.m4v', '.3gp', '.wmv'}
    ext = os.path.splitext(file_path)[1].lower()
    is_video = ext in video_extensions

    audio_path = file_path
    tmp_extract = None

    if is_video:
        import shutil as _shutil
        ffmpeg_path = _shutil.which("ffmpeg")
        if ffmpeg_path:
            try:
                import subprocess as _sp
                tmp_extract = os.path.join(
                    os.path.dirname(file_path),
                    f"_analyze_tmp_{os.path.basename(file_path)}.wav",
                )
                result = _sp.run(
                    [ffmpeg_path, "-y", "-i", file_path,
                     "-vn", "-acodec", "pcm_s16le", "-ar", "44100",
                     "-ac", "1", tmp_extract],
                    capture_output=True, timeout=60,
                )
                if result.returncode == 0 and os.path.isfile(tmp_extract):
                    audio_path = tmp_extract
            except Exception:
                pass
            finally:
                if tmp_extract and not os.path.isfile(tmp_extract):
                    tmp_extract = None

    try:
        import librosa as _librosa
        import numpy as _np

        y, sr = _librosa.load(audio_path, duration=30, res_type="kaiser_fast", mono=True)

        result = {
            "sample_rate": sr,
            "duration_sec": round(len(y) / sr, 2),
            "bpm": None,
            "key": None,
            "video_file": is_video,
        }

        if len(y) >= sr:
            try:
                tempo, _ = _librosa.beat.beat_track(y=y, sr=sr)
                bpm = float(tempo.item() if hasattr(tempo, 'item') else tempo)
                if bpm > 0:
                    result["bpm"] = round(bpm, 1)
            except Exception:
                pass

            try:
                chroma = _librosa.feature.chroma_cqt(y=y, sr=sr)
                chroma_mean = chroma.mean(axis=1)
                major_profile = _np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
                minor_profile = _np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
                key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                best_corr = -1.0
                best_key = ""
                for i in range(12):
                    corr_major = _np.corrcoef(_np.roll(major_profile, i), chroma_mean)[0, 1]
                    corr_minor = _np.corrcoef(_np.roll(minor_profile, i), chroma_mean)[0, 1]
                    if corr_major > best_corr:
                        best_corr = corr_major
                        best_key = f"{key_names[i]} major"
                    if corr_minor > best_corr:
                        best_corr = corr_minor
                        best_key = f"{key_names[i]} minor"
                if best_corr > 0.1:
                    result["key"] = best_key
            except Exception:
                pass

        try:
            y_full, _ = _librosa.load(audio_path, sr=None, mono=True)
            target_samples = min(8000, len(y_full))
            indices = _np.linspace(0, len(y_full) - 1, target_samples, dtype=int)
            waveform = y_full[indices].astype(_np.float32).tolist()
            result["waveform"] = waveform
            result["waveform_samples"] = len(waveform)
            result["full_duration_sec"] = round(len(y_full) / (sr or 44100), 2)
        except Exception:
            result["waveform"] = []
            result["waveform_samples"] = 0

        return {"status": "ok", "analysis": result}

    except Exception as e:
        err_msg = str(e)
        if "sndfile" in err_msg.lower() or "soundfile" in err_msg.lower():
            err_msg = "Unsupported audio format — try converting to WAV first"
        elif "ffmpeg" in err_msg.lower():
            err_msg = "FFmpeg not found — install FFmpeg or convert to WAV first"
        raise HTTPException(500, f"Analysis failed: {err_msg}")
    finally:
        if tmp_extract and os.path.exists(tmp_extract):
            try:
                os.remove(tmp_extract)
            except Exception:
                pass


# ── Stem Preview / Export / MIDI ─────────────────────────────────────



class StemMixRequest(BaseModel):
    folder_name: str
    volumes: dict[str, float] = {}
    master_volume: float = 1.0

@app.post("/api/stems/preview")
async def stem_preview(req: StemMixRequest):
    """Mix stems and return a short WAV preview (15 seconds)."""
    folder_path = os.path.join(OUTPUT_DIR, req.folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(404, "Folder not found")

    stem_suffixes = {"vocals", "drums", "bass", "other", "guitar", "piano"}
    stem_files = []
    for f in os.listdir(folder_path):
        f_lower = f.lower()
        for suffix in stem_suffixes:
            if suffix in f_lower and f.endswith((".wav", ".mp3", ".flac")):
                stem_files.append(os.path.join(folder_path, f))
                break

    if not stem_files:
        raise HTTPException(404, "No stem files found")

    try:
        import io
        import soundfile as _sf
        import numpy as _np

        master = req.master_volume
        mixed = None
        target_sr = 44100
        preview_len = 15

        for stem_path in stem_files:
            key = os.path.basename(stem_path).lower()
            vol = master
            for sk, sv in req.volumes.items():
                if sk.lower() in key:
                    vol *= sv
                    break
            if vol < 0.01:
                continue
            data, file_sr = _sf.read(stem_path, dtype="float32")
            if data.ndim == 1:
                data = data[:, _np.newaxis]
            data = data[:int(preview_len * file_sr)]
            if mixed is None:
                mixed = data * vol
            else:
                min_len = min(mixed.shape[0], data.shape[0])
                mixed = mixed[:min_len] + data[:min_len] * vol

        if mixed is None:
            raise HTTPException(400, "No stems to mix (all volumes too low)")

        buf = io.BytesIO()
        _sf.write(buf, mixed, target_sr, format="WAV")
        buf.seek(0)
        return Response(content=buf.read(), media_type="audio/wav",
                        headers={"Content-Disposition": "inline; filename=preview.wav"})

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Preview failed: {e}")



class StemExportRequest(BaseModel):
    folder_name: str
    volumes: dict[str, float] = {}
    master_volume: float = 1.0
    output_format: str = "wav"

@app.post("/api/stems/export")
async def stem_export(req: StemExportRequest):
    """Mix stems and export to a file."""
    folder_path = os.path.join(OUTPUT_DIR, req.folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(404, "Folder not found")

    stem_suffixes = {"vocals", "drums", "bass", "other", "guitar", "piano"}
    stem_files = []
    for f in os.listdir(folder_path):
        f_lower = f.lower()
        for suffix in stem_suffixes:
            if suffix in f_lower and f.endswith((".wav", ".mp3", ".flac")):
                stem_files.append(os.path.join(folder_path, f))
                break

    if not stem_files:
        raise HTTPException(404, "No stem files found")

    try:
        import soundfile as _sf
        import numpy as _np

        master = req.master_volume
        mixed = None
        target_sr = 44100

        for stem_path in stem_files:
            key = os.path.basename(stem_path).lower()
            vol = master
            for sk, sv in req.volumes.items():
                if sk.lower() in key:
                    vol *= sv
                    break
            if vol < 0.01:
                continue
            data, file_sr = _sf.read(stem_path, dtype="float32")
            if data.ndim == 1:
                data = data[:, _np.newaxis]
            if mixed is None:
                mixed = data * vol
            else:
                min_len = min(mixed.shape[0], data.shape[0])
                mixed = mixed[:min_len] + data[:min_len] * vol

        if mixed is None:
            raise HTTPException(400, "No stems to mix")

        ext = req.output_format
        out_path = os.path.join(folder_path, f"stem_mix.{ext}")
        _sf.write(out_path, mixed, target_sr)

        size_mb = round(os.path.getsize(out_path) / (1024 * 1024), 2)
        return {"status": "ok", "file_path": out_path, "filename": f"stem_mix.{ext}", "size_mb": size_mb}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Export failed: {e}")



class StemExportSeparateRequest(BaseModel):
    folder_name: str
    volumes: dict[str, float] = {}
    master_volume: float = 1.0
    output_format: str = "wav"

@app.post("/api/stems/export_separate")
async def stem_export_separate(req: StemExportSeparateRequest):
    """Export each stem at custom level as separate file."""
    folder_path = os.path.join(OUTPUT_DIR, req.folder_name)
    if not os.path.isdir(folder_path):
        raise HTTPException(404, "Folder not found")

    stem_suffixes = {"vocals", "drums", "bass", "other", "guitar", "piano"}
    ext = req.output_format
    master = req.master_volume
    exported = []

    for f in os.listdir(folder_path):
        f_lower = f.lower()
        matched = None
        for suffix in stem_suffixes:
            if suffix in f_lower and f.endswith((".wav", ".mp3", ".flac")):
                matched = suffix
                break
        if not matched:
            continue

        stem_path = os.path.join(folder_path, f)
        vol = master
        for sk, sv in req.volumes.items():
            if sk.lower() in matched:
                vol *= sv
                break

        try:
            import soundfile as _sf
            data, sr = _sf.read(stem_path, dtype="float32")
            if vol != 1.0:
                data = data * vol
            stem_name = os.path.splitext(f)[0]
            out_path = os.path.join(folder_path, f"{stem_name}_custom.{ext}")
            _sf.write(out_path, data, sr)
            exported.append({"filename": f"{stem_name}_custom.{ext}",
                             "size_mb": round(os.path.getsize(out_path) / (1024 * 1024), 2)})
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Export of {f} failed: {e}")

    return {"status": "ok", "files": exported}



class MidiRequest(BaseModel):
    file_path: str

@app.post("/api/stems/midi")
async def stem_to_midi(req: MidiRequest):
    """Extract MIDI from a melodic stem file."""
    file_path = req.file_path
    if not os.path.isfile(file_path):
        raise HTTPException(404, "File not found")

    try:
        import soundfile as _sf
        import librosa as _librosa
        import numpy as _np

        y, sr = _sf.read(file_path, dtype="float32")
        if y.ndim == 2:
            y = y.mean(axis=1)

        fmin = _librosa.note_to_hz("C2")
        fmax = _librosa.note_to_hz("C7")
        f0, voiced, _ = _librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr)
        times = _librosa.times_like(f0, sr=sr)

        onset_frames = _librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
        onset_times = _librosa.frames_to_time(onset_frames, sr=sr)
        midi_notes = []

        for i in range(len(onset_times)):
            t_start = onset_times[i]
            t_end = onset_times[i + 1] if i + 1 < len(onset_times) else times[-1]
            if t_end - t_start < 0.05:
                continue
            mask = (times >= t_start) & (times < t_end) & voiced
            if not mask.any():
                continue
            freq = f0[mask]
            if len(freq) == 0:
                continue
            pitch_hz = float(np.median(freq))
            midi_note = int(round(12 * np.log2(pitch_hz / 440.0) + 69))
            midi_note = max(0, min(127, midi_note))
            velocity = min(100, int(np.median(voiced[mask]) * 80 + 20))
            midi_notes.append({"pitch": midi_note, "start": round(t_start, 3), "end": round(t_end, 3), "velocity": velocity})

        out_dir = os.path.dirname(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        midi_path = os.path.join(out_dir, f"{base}.mid")

        if midi_notes:
            _write_midi(midi_notes, midi_path)

        return {
            "status": "ok",
            "midi_path": midi_path if midi_notes else None,
            "notes": len(midi_notes),
            "filename": os.path.basename(midi_path) if midi_notes else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"MIDI extraction failed: {e}")


def _write_midi(notes: list[dict], output_path: str, tempo: int = 120):
    """Write a simple single-track MIDI file."""
    ticks_per_beat = 480
    microsec_per_beat = 60_000_000 // tempo

    all_notes = []
    for n in notes:
        start_tick = int(n["start"] * tempo * ticks_per_beat / 60)
        end_tick = int(n["end"] * tempo * ticks_per_beat / 60)
        if end_tick <= start_tick:
            end_tick = start_tick + ticks_per_beat // 8
        all_notes.append((n["pitch"], start_tick, end_tick, n["velocity"]))

    if not all_notes:
        return

    max_tick = max(n[2] for n in all_notes)
    data = bytearray()
    data.extend(b"MThd")
    data.extend((0, 0, 0, 6))
    data.extend((0, 1))
    data.extend((0, 2))
    data.extend((ticks_per_beat >> 8, ticks_per_beat & 0xFF))

    data.extend(b"MTrk")
    track0 = bytearray()
    track0.extend((0, 0xFF, 0x51, 3))
    track0.extend((microsec_per_beat >> 16, (microsec_per_beat >> 8) & 0xFF, microsec_per_beat & 0xFF))
    track0.extend((0, 0xFF, 0x2F, 0))
    data.extend((len(track0) >> 24, (len(track0) >> 16) & 0xFF, (len(track0) >> 8) & 0xFF, len(track0) & 0xFF))
    data.extend(track0)

    data.extend(b"MTrk")
    track1 = bytearray()
    all_notes.sort(key=lambda n: n[1])
    current_time = 0

    def write_vlq(buf, value):
        v = value
        bytes_arr = []
        bytes_arr.append(v & 0x7F)
        while v > 0x7F:
            v >>= 7
            bytes_arr.append((v & 0x7F) | 0x80)
        for b in reversed(bytes_arr):
            buf.append(b)

    for pitch, start_tick, end_tick, vel in all_notes:
        delta = start_tick - current_time
        write_vlq(track1, delta)
        track1.extend((0x90, pitch, vel))
        delta = end_tick - start_tick
        write_vlq(track1, delta)
        track1.extend((0x80, pitch, 0))
        current_time = end_tick

    write_vlq(track1, max(0, max_tick - current_time))
    track1.extend((0xFF, 0x2F, 0))
    data.extend((len(track1) >> 24, (len(track1) >> 16) & 0xFF, (len(track1) >> 8) & 0xFF, len(track1) & 0xFF))
    data.extend(track1)

    with open(output_path, "wb") as f:
        f.write(data)


# ── WebSocket for real-time progress ──────────────────────────────────

_MAX_WS_CONNECTIONS = 4  # Max simultaneous WebSocket clients
_WS_HEARTBEAT_INTERVAL = 15  # Server-side ping interval (seconds)
_WS_HEARTBEAT_TIMEOUT = 30  # Close if no pong received within this (seconds)


@app.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """WebSocket endpoint for real-time separation progress (per-job).

    Features:
    - Connection limit: rejects clients beyond _MAX_WS_CONNECTIONS to
      prevent socket exhaustion from runaway clients.
    - Server-side heartbeat: sends ping every _WS_HEARTBEAT_INTERVAL;
      closes the connection if the client hasn't responded within
      _WS_HEARTBEAT_TIMEOUT seconds (stale connection cleanup).
    """
    # ── Reject if too many connections ──
    with _progress_lock:
        if len(_progress_connections) >= _MAX_WS_CONNECTIONS:
            logger.warning(
                "WebSocket rejected: %d connections (limit %d)",
                len(_progress_connections), _MAX_WS_CONNECTIONS,
            )
            await websocket.close(code=1013, reason="Too many connections")
            return

    await websocket.accept()
    with _progress_lock:
        _progress_connections.append(websocket)
    logger.info("WebSocket client connected (%d total)", len(_progress_connections))

    last_pong = time.time()

    try:
        while True:
            try:
                # Wait for a message, but timeout periodically to check
                # if the client is still alive (heartbeat).
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=_WS_HEARTBEAT_INTERVAL,
                )
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    last_pong = time.time()
                elif data == "pong":
                    last_pong = time.time()
            except asyncio.TimeoutError:
                # No message received within heartbeat interval — send a
                # ping to check if client is alive.
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
                # Give the client _WS_HEARTBEAT_TIMEOUT - _WS_HEARTBEAT_INTERVAL
                # seconds to respond before we consider it dead.
                try:
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=_WS_HEARTBEAT_TIMEOUT - _WS_HEARTBEAT_INTERVAL,
                    )
                    if data in ("ping", "pong"):
                        last_pong = time.time()
                except asyncio.TimeoutError:
                    # Client didn't respond — stale connection, close it.
                    logger.info("WebSocket stale (no heartbeat response), closing")
                    break
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        with _progress_lock:
            try:
                _progress_connections.remove(websocket)
            except ValueError:
                pass
        logger.info("WebSocket client disconnected (%d remaining)", len(_progress_connections))


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
