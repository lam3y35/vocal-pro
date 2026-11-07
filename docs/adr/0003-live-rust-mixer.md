# ADR-0003: Replace Server-Side HTTP WAV Preview with Real-Time Rust Stem Mixer

- **Status:** Accepted (`[V]`)
- **Date:** 2026-11-07
- **Fixes:** `P-01`, `P-09`

## Context
In the legacy application (`api_server/main.py:995-1068` and `flutter_app/lib/screens/results_screen.dart`):
1. Every time the user adjusted stem volume sliders and clicked "Preview 15s", the UI called `POST /api/outputs/{folder}/stem_preview`.
2. The Python server synchronously read up to 6 full stem audio files from disk (`sf.read`), mixed 15 seconds in NumPy, encoded a 16-bit PCM WAV into a `BytesIO` buffer, and sent the multi-megabyte WAV over HTTP (`P-09`), blocking the FastAPI event loop (`P-01`).

## Decision
1. Implement a real-time multi-stem audio mixer in Rust (`src-tauri/src/audio/mixer.rs` and `export.rs`).
2. Decode all stems of the loaded output folder into planar/interleaved `f32` sample buffers in memory (resampled to output device rate if needed via `rubato`).
3. Store per-stem `gain` (`0.0..=2.0`), `mute` (`bool`), `solo` (`bool`), and shared `playhead_frame` (`AtomicUsize`) using lock-free atomics (`std::sync::atomic`).
4. In the real-time audio callback (`cpal` when a hardware output device is present, with automatic fallback to WebAudio streamed frames or offline preview buffer in headless/CI environments without ALSA hardware):
   - Sum active stems per frame (`sample += stem[i][frame] * effective_gain`),
   - Apply soft-clipping (`sample.clamp(-0.99, 0.99)` when peak > `0.99`),
   - Zero heap allocations, zero locks, zero disk I/O inside the audio callback.
5. Implement `export_mix` and `export_separate_stems` natively in Rust (`export.rs`) using the exact same summing and peak-normalization math (`mixed / peak * 0.99` when `peak > 0.99`) and encoding to WAV (`hound`), FLAC, or MP3 (`ffmpeg` CLI with `-b:a <bitrate>`).

## Consequences
- Fader-to-audio latency drops from ~800–2,000 ms (HTTP round-trip + disk read) to < 15 ms (`N8`, `MIX-01`, `MIX-02`).
- Exported mixes match live playback bit-for-bit (`MIX-03`).
