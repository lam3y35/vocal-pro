# ADR-0001: Replace Localhost FastAPI/WebSocket Server with Persistent Stdio JSON-Lines Worker

- **Status:** Accepted (`[V]`)
- **Date:** 2026-11-07
- **Fixes:** `P-01`, `P-03`, `P-04`, `P-10`, `P-11`, `P-12`

## Context
In the legacy architecture (`api_server/main.py` + `flutter_app/lib/services/backend_service.dart`):
1. The UI spawned `python -m uvicorn api_server.main:app --port 8000` (`backend_service.dart:61`), slept a hardcoded 3 seconds (`backend_service.dart:72`), and polled `http://127.0.0.1:8000/api/health` every 2 seconds (`backend_service.dart:116`).
2. Multiple `async def` endpoints (`analyze_audio`, `stem_preview`, `stem_export`, `stem_to_midi`, `download_url`) ran CPU-heavy synchronous operations directly on the asyncio event loop (`P-01`), freezing health checks and WebSocket broadcasts.
3. `_run_demucs_on_file` (`code/separation_engine.py:1024-1060`) spawned an extra Python subprocess that looped `time.sleep(2)` and sent fake HTTP `POST /api/jobs/{id}/progress` requests (`P-03`), which `api_server/main.py:659` never even broadcast over WebSocket (`P-04`).
4. Ephemeral port churn on Windows caused `WinError 10055` socket exhaustion (`P-12`), and `/api/upload` duplicated large input files into `%APPDATA%/VocalPro/uploads` (`P-11`).

## Decision
1. Eliminate `uvicorn`, `fastapi`, `websockets`, and all TCP/HTTP listening sockets (`N4`).
2. Spawn a single persistent Python child process (`python -m vocalpro_worker`) with `stdin`, `stdout`, and `stderr` piped directly to the Tauri Rust core.
3. Exchange strict, schema-validated (`schemas/worker-protocol.schema.json`), versioned (`"v": 1`) UTF-8 JSON-Lines messages over `stdin` (Rust -> Worker) and `stdout` (Worker -> Rust).
4. Redirect all library `stdout` writes inside the worker to `sys.stderr` at startup (`sys.stdout = sys.stderr`) while keeping a dedicated binary-flushed `os.fdopen(orig_stdout_fd, "wb", buffering=0)` channel exclusively for protocol frames.
5. Pass local file paths directly in `separate`, `analyze`, and `stem_to_midi` commands without copying files.

## Consequences
- Zero open network ports (`N4` satisfied).
- Sub-second startup handshake (`ready` frame emitted immediately upon worker initialization, replacing the 3s+2.5s+1.5s startup delays).
- Real-time per-segment progress events streamed over `stdout` directly into Tauri events (`N5` satisfied).
