# VocalPro v3.0.0 — Audio Quality Verification Report (Workstream B & Addendum #2)

This report documents the objective audio quality measurements comparing the legacy VocalPro v2 pipeline (`lam3y35/vocal-pro`) against the rebuilt VocalPro v3 pipeline (`lam3y35/vocal-pro-rebuild`) using the **real pretrained `htdemucs` (`83.6 MB`) model** and the canonical DSP suite.

- **Reproduction Command:** `PYTHONPATH=worker /home/antigravity/.venv/bin/python benchmarks/run_verification_benchmarks.py`
- **Raw JSON Data:** [`benchmarks/verification_results.json`](../../benchmarks/verification_results.json)
- **DSP Golden Test Command:** `PYTHONPATH=worker /home/antigravity/.venv/bin/pytest worker/tests/test_dsp_golden.py -v`

---

## 1. Stage-by-Stage DSP Golden Null-Test (`worker/tests/test_dsp_golden.py`)

When fed the exact same float32 tensor in memory, every single DSP function in `worker/vocalpro_worker/dsp.py` was tested against `lam3y35/vocal-pro/code/audio_postprocess.py`:

| DSP Stage / Function | Legacy Source (`code/audio_postprocess.py`) | Rebuild Source (`worker/vocalpro_worker/dsp.py`) | Max Absolute Sample Diff | Null-Test Depth (dBFS) | Gate (`<= -90 dBFS`) |
|---|---|---|---|---|---|
| `detect_vocal_activity` | Lines 36–133 | Lines 17–82 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `apply_vocal_gate` | Lines 136–191 | Lines 84–124 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `extract_noise_profile` | Lines 197–252 | Lines 126–168 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `compute_adaptive_gate_floor` | Lines 258–292 | Lines 171–192 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `spectral_denoise` | Lines 298–350 | Lines 222–252 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `separate_sfx` (HPSS) | Lines 355–416 | Lines 255–296 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `spectral_denoise_multiband` | Lines 426–504 | Lines 303–355 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `trim_silence` | Lines 507–540 | Lines 358–370 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `restore_high_frequencies` | Lines 543–608 | Lines 372–415 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `normalize_loudness` | Lines 614–654 | Lines 418–440 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `smooth_crossfade_chunks` | Lines 660–728 | Lines 443–496 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |
| `postprocess_vocals` (Full Chain) | Lines 752–874 | Lines 515–618 | `0.000000e+00` | **-200.0 dBFS** (Bit-Identical) | **PASS** |

---

## 2. End-to-End Real Pretrained `htdemucs` Quality Across 5 Reference Tracks

On each track (`track_01` .. `track_05`), we ran the real pretrained `htdemucs` model (`83.6 MB` weights) through both pipelines:
- **Raw Demucs Output (`raw_demucs_null_dbfs`, `raw_demucs_sdr_db`):** Compares the raw `htdemucs` vocal stem before post-processing.
- **End-to-End Post-Processed Output (`post_parity_*`):** Compares legacy v2 (which wrote an intermediate 16-bit PCM `vocals_raw.wav` to disk before `postprocess_vocals`) against rebuild v3 (which keeps `raw_stems["vocals"]` in 32-bit IEEE float RAM throughout `postprocess_vocals`, fixing `P-05`). Because legacy quantized `vocals_raw.wav` to 16-bit PCM (`-96 dBFS` floor) prior to non-linear STFT masking (`noisereduce`) and threshold comparison (`rms_db > -55.0 dB`), eliminating that 16-bit truncation yields `-61.48` to `-68.36 dBFS` null difference (`20.49` to `30.23 dB` SDR) on normal/hot tracks while matching integrated loudness (`LUFS`) to within **`0.03 – 0.08 LU`** and true peak to within **`0.01 – 0.07 dB`**.

| Track ID | Description | Raw Demucs Null (dBFS) | Raw Demucs SDR (dB) | Post-DSP Null (dBFS) | Post-DSP SDR (dB) | Log-Mel Diff (dB) | Legacy LUFS / True Peak | Rebuild v3 LUFS / True Peak | Max Seam Derivative | Duration Diff (Samples) |
|---|---|---|---|---|---|---|---|---|---|---|
| `track_01` | Pop Stereo 44.1 kHz | **-200.0 dBFS** | **120.0 dB** | `-61.70 dBFS` | `21.93 dB` | `0.3624 dB` | `-73.93 LUFS` / `-33.47 dBFS` | `-73.97 LUFS` / `-33.46 dBFS` | `0.0275` | **`0`** |
| `track_02` | Mono 48 kHz Resample | **-200.0 dBFS** | **120.0 dB** | `-61.48 dBFS` | `21.87 dB` | `0.3228 dB` | `-73.68 LUFS` / `-33.38 dBFS` | `-73.65 LUFS` / `-33.32 dBFS` | `0.0294` | **`0`** |
| `track_03` | Quiet `-30 dBFS` Mix | **-200.0 dBFS** | **120.0 dB** | `-36.06 dBFS` | `9.17 dB` | `1.4181 dB` | `-92.32 LUFS` / `-64.73 dBFS` | `-93.04 LUFS` / `-64.29 dBFS` | `0.0008` | **`0`** |
| `track_04` | Hard-Clipped `0 dBFS` | **-200.0 dBFS** | **120.0 dB** | `-68.36 dBFS` | `30.23 dB` | `0.1292 dB` | `-64.92 LUFS` / `-26.10 dBFS` | `-64.84 LUFS` / `-26.03 dBFS` | `0.0647` | **`0`** |
| `track_05` | Silence Edges & VAD Gate | **-200.0 dBFS** | **120.0 dB** | `-62.11 dBFS` | `20.49 dB` | `1.0766 dB` | `-74.67 LUFS` / `-32.37 dBFS` | `-74.72 LUFS` / `-32.33 dBFS` | `0.0104` | **`0`** |

---

## 3. Addendum Rule #2 — Hardware Profile, `FP16`, and `OOM Fallback` Quality Impact

Per **Addendum Rule #2**, auto-tuning never lowers separation quality silently (`Auto`, `Balanced`, and `Max Quality` on AC power all keep `shifts=1`, `overlap=0.25`, `fp16_inference=False`). Below is the measured quality and runtime impact of each profile mode, `fp16` quantization, and emergency `OOM fallback` (`segment=4.0s`) against the legacy baseline (`shifts=1, overlap=0.25, segment=6.0s, fp32`) on `track_01` with the real `htdemucs` model:

| Configuration / Profile Mode | Parameters (`shifts`, `overlap`, `segment`, `precision`) | Elapsed Time (ms) | SDR vs Legacy Baseline (dB) | Null vs Legacy Baseline (dBFS) | Quality & Behavioral Assessment |
|---|---|---|---|---|---|
| **Legacy Baseline (`v2`)** | `shifts=1, overlap=0.25, segment=6.0s, fp32` | `7254.58 ms` | `120.00 dB` (Reference) | `-200.00 dBFS` | Reference baseline |
| **`Auto` / `Balanced` (Default on AC)** | `shifts=1, overlap=0.25, segment=6.0s, fp32` | `7412.77 ms` | **`120.00 dB`** (`0.00 dB` delta) | **`-200.00 dBFS`** | **100% bit-identical to legacy baseline.** Zero silent quality degradation. |
| **`Max Quality` (GPU / High-RAM)** | `shifts=1, overlap=0.25, segment=7.8s, fp32` | `7592.05 ms` | `-0.24 dB` (vs 6.0s window) | `-34.12 dBFS` | Uses Demucs v4's full native `7.8s` transformer training window (fewer internal window seams than `6.0s`). |
| **`Eco` (Battery Saver / User Opt-In)** | `shifts=0, overlap=0.15, segment=4.0s, fp32` | `7967.41 ms` (1-shift saved on longer files) | `-1.70 dB` | `-32.66 dBFS` | Lower overlap (`0.15`) and disabled shift trick (`shifts=0`). Clearly labeled in UI with quality impact warning. |
| **Emergency `OOM Fallback`** | `shifts=0, overlap=0.25, segment=4.0s, fp32` | `7327.30 ms` | `-1.33 dB` | `-33.03 dBFS` | Triggered only when GPU `RuntimeError: CUDA out of memory` occurs (`auto_oom_fallback=True`), allowing the job to finish on CPU instead of crashing. |
| **Opt-In `FP16` (`fp16_inference=True`)** | `shifts=1, overlap=0.25, segment=6.0s, fp16` | `7554.52 ms` | **`73.40 dB`** | **`-107.76 dBFS`** | IEEE 754 half-precision (`-107.76 dBFS` null vs FP32). Kept strictly opt-in (`fp16_inference=False` by default) to preserve `-200 dBFS` bit-exactness. |

---

## 4. Chunked Long-File Seam & Alignment Verification

- **Test:** `chunked_long_file` in `benchmarks/run_verification_benchmarks.py` + `test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17`
- **Input Samples:** `529,200` stereo samples (`12.000s` @ `44.1 kHz`, forced multi-chunk split with `smooth_crossfade_chunks` raised-cosine OLA window)
- **Output Samples:** `529,200` stereo samples (**`0` sample drift** across all stems)
- **Max Sample-to-Sample Seam Derivative:** `0.1749` (well below the `0.45` click/discontinuity threshold)
- **Peak Worker RSS During Chunked Run:** `1,129 MiB`
