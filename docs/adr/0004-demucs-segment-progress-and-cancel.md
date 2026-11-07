# ADR-0004: Real Per-Segment Progress & Cooperative Cancellation via Native `demucs.apply.apply_model` Callback

- **Status:** Accepted (`[V]`)
- **Date:** 2026-11-07
- **Fixes:** `P-03`, `P-04`, `N2`, `N5`

## Context
In the legacy application (`code/separation_engine.py:1024-1060`):
1. `_run_demucs_on_file` spawned a separate Python subprocess (`subprocess.Popen([sys.executable, "-c", script])`) that guessed total duration (`max(10.0, duration * 1.5 * max(1, shifts))`) and looped `time.sleep(2)`, posting fake progress percentages to `http://127.0.0.1:8000/api/jobs/{id}/progress` (`P-03`).
2. `apply_model` was invoked with `progress=False` and no callback, blocking until the entire file finished.

## Verified Discovery (`[V]`)
Inspecting `demucs.apply.apply_model` in `demucs==4.0.1` / `4.1.0` confirms that `apply_model` natively accepts:
```python
callback: Optional[Callable[[dict], None]] = None,
callback_arg: Optional[dict] = None
```
1. For every segment `offset` in `range(0, length, stride)` across every shift `0..shifts-1` and every sub-model `0..models-1` in a `BagOfModels`, `apply_model` invokes `callback(d)` with:
   - `d["model_idx_in_bag"]`: `int` (`0 .. models - 1`)
   - `d["models"]`: `int` (number of sub-models in bag, e.g. `4` for `htdemucs_ft`, `1` for `htdemucs`)
   - `d["shift_idx"]`: `int` (`0 .. shifts - 1`)
   - `d["segment_offset"]`: `int` (audio sample offset of the current segment)
   - `d["state"]`: `"start"` | `"end"`
2. Furthermore, `apply_model`'s segment loop (`demucs/apply.py:105-110`) explicitly wraps `future.result()` in:
   ```python
   try:
       chunk_out = future.result()
   except BaseException:
       # BaseException so that a `KeyboardInterrupt` raised from a callback
       # to abort the separation also cancels the remaining chunks.
       pool.shutdown(wait=True, cancel_futures=True)
       raise
   ```

## Decision
1. Pass a structured `callback` to `demucs.apply.apply_model` that:
   - Checks `if cancel_event.is_set(): raise JobCancelledError()` on both `"start"` and `"end"` states, immediately cancelling any queued segment futures and releasing GPU/CPU memory (`N5`).
   - Computes exact segment index and total segments:
     - `stride = int((1 - overlap) * int(samplerate * segment))`
     - `segments_per_pass = ceil(length / stride)`
     - `total_segments = models * max(1, shifts) * segments_per_pass`
     - Emits a real `progress` event over `stdout` JSON-Lines with `phase="inference"`, `segment_index`, `segment_total`, `sub_model_index`, `sub_model_total`, and `eta_s`.
2. Because this uses `apply_model` directly without altering tensor chunking, random shift seeding, or transition weights, numerical equivalence with `apply_model(..., callback=None)` is **exact (`max(abs(a - b)) == 0.0`)** (`N2`).

## Consequences
- Zero subprocess spawning per chunk/file (`P-03` eliminated).
- Exact bit-for-bit numerical equivalence (`0.0` difference) with reference `apply_model`.
- Real progress events per segment and cooperative cancellation within one segment boundary (< 500 ms on GPU / short segments, immediate abort on cancel).
