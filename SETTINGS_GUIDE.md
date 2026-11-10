# VocalPro v3 — Complete Audio Settings & Fine-Tuning Guide

> **Target Audience:** Audio Producers, Sound Engineers, DJs, Content Creators, and Vocalists.  
> **Purpose:** Detailed reference explaining every setting in VocalPro v3, how each parameter mathematically alters the audio signal, and concrete before/after examples demonstrating how to achieve pristine, studio-grade vocal separation.

---

## 📑 Table of Contents
1. [Core AI Separation & Neural Models](#1-core-ai-separation--neural-models)
2. [Acoustic Quality & Artifact Suppression (TTA & Overlap)](#2-acoustic-quality--artifact-suppression)
3. [Vocal Noise Gating & Bleed Isolation](#3-vocal-noise-gating--bleed-isolation)
4. [Spectral Denoising & Multi-Band Filtering](#4-spectral-denoising--multi-band-filtering)
5. [High-Frequency Air & Clarity Restoration (HF Restore)](#5-high-frequency-air--clarity-restoration)
6. [Harmonic-Percussive SFX Separation (HPSS)](#6-harmonic-percussive-sfx-separation)
7. [Hardware Calibration, Memory Caps & Speed Tuning](#7-hardware-calibration-memory-caps--speed-tuning)
8. [Turnkey Preset Recipes for Common Scenarios](#8-turnkey-preset-recipes-for-common-scenarios)

---

## 1. Core AI Separation & Neural Models

VocalPro v3 uses deep recurrent and convolutional neural networks trained on multitrack studio stems to perform source separation in both the time and frequency domains.

```
Mixed Audio (Stereo / 44.1kHz)
   │
   ├──▶ Neural Network Backbone (Demucs / MDX)
   │        ├── Vocals Stem
   │        ├── Drums Stem
   │        ├── Bass Stem
   │        └── Other (Guitars, Synths, Strings)
   │
   └──▶ DSP Post-Processing Chain (Gate ➔ Denoise ➔ HF Restore ➔ Normalize)
```

### `model_name` (Neural Network Architecture)
* **Default:** `htdemucs`
* **Options:** `htdemucs`, `htdemucs_ft`, `htdemucs_6s`, `mdx_extra`, `mdx_extra_q`
* **What it does:** Selects the mathematical weight model loaded by PyTorch.
  * **`htdemucs` (Hybrid Transformer):** 4-stem separation (Vocals, Drums, Bass, Other). Excellent balance of speed and fidelity. Recommended for general music.
  * **`htdemucs_ft` (Fine-Tuned):** Higher resolution weights trained for 4x more epochs. Delivers noticeably clearer vocal boundaries with less instrumental bleed at the cost of ~25% slower inference.
  * **`htdemucs_6s` (6-Stem Studio Edition):** Isolates **6 distinct stems**: Vocals, Drums, Bass, Other, **Piano**, and **Guitar**. Essential when you need acoustic piano or guitar isolated from vocals.
  * **`mdx_extra` (Multi-Domain CrossNet):** Emphasizes complex vocal harmonies and back-vocals separation.

#### 🎧 Audio Effect & Examples:
* **Scenario A:** Standard Pop/Rock song with acoustic piano.
  * *Using `htdemucs`:* Piano notes will bleed into the "Other" and slightly into the "Vocals" stem.
  * *Using `htdemucs_6s`:* The piano is extracted onto its own dedicated track, leaving the vocal stem 100% clean of piano resonance.

---

## 2. Acoustic Quality & Artifact Suppression

These parameters control **Test-Time Augmentation (TTA)** and sliding-window analysis.

### `shifts` (Test-Time Augmentation Shift Count)
* **Range:** `0` to `5` (Default: `1`)
* **What it does:** When `shifts > 0`, VocalPro shifts the incoming audio waveform randomly along the time axis, runs the neural net on each shifted version, shifts them back, and averages the spectrograms.
* **Why it matters:** Neural networks are slightly sensitive to the exact phase and sample alignment of transients. Shifting and averaging eliminates phase cancellations.

#### 🎧 Audio Impact:
* **`shifts = 0` (Fast Mode):** Fastest processing (1x time). You may hear subtle metallic "phase smearing" or "comb filtering" on sustained vocal notes.
* **`shifts = 1` (Recommended Default):** 2x inference passes. Completely removes phase roughness. Vocals sound natural, warm, and clear.
* **`shifts = 2` to `3` (Mastering Quality):** 3x to 4x inference passes. Ultra-smooth acapella, zero phase flutter, ideal for final broadcast release or sampling.

---

### `overlap` (Sliding Window Overlap Ratio)
* **Range:** `0.10` (10%) to `0.75` (75%) (Default: `0.25` / 25%)
* **What it does:** Controls how much adjacent 6-second audio segments overlap when passed through the AI engine. Overlapping segments are crossfaded using cosine windowing.

#### 🎧 Audio Impact:
* **Too low (`< 0.15`):** You might hear faint volume "pulsing" or rhythmic dips every 6 seconds where segments join.
* **Recommended (`0.25`):** Transparent crossfades with zero seam perception.
* **High (`0.50`):** 50% overlap. Flawless continuity for classical, ambient, or slow ballad vocals with long reverbs.

---

### `segment` (Chunk Duration in Seconds)
* **Range:** `4.0` to `12.0` (Default: `6.0` s)
* **What it does:** The temporal window size sent to the GPU in each batch.
* **Hardware Impact:**
  * Lower segment (`4.0` s) reduces GPU VRAM consumption to under 2 GB (prevents Out-Of-Memory errors on entry-level GPUs or integrated graphics).
  * Higher segment (`7.8` s) gives the AI more musical context (better detection of long vibrato or vocal delays).

---

## 3. Vocal Noise Gating & Bleed Isolation

When a singer is silent between verses, neural networks often leave faint traces of cymbals, bass rumble, or guitar harmonics. VocalPro includes a specialized vocal activity detector and dynamic gate.

```
Vocal Stem Input ──▶ [RMS & Spectral Flatness VAD]
                            │
                            ├── Is Voice Present?
                            │      ├── YES ──▶ 0 dB Gain (Unchanged Voice)
                            │      └── NO  ──▶ Attenuate to Gate Floor (-60 dB)
```

### `enable_vocal_gate`
* **Type:** Boolean (`true` / `false`, Default: `true`)
* **What it does:** Activates automatic silence gating between vocal phrases.

### `gate_threshold_db`
* **Range:** `-70.0 dB` to `-30.0 dB` (Default: `-55.0 dB`)
* **What it does:** The volume sensitivity threshold for detecting human voice.
  * If the audio level exceeds this threshold and matches vocal spectral characteristics (spectral flatness check), the gate opens.

### `gate_floor_db`
* **Range:** `-90.0 dB` to `-30.0 dB` (Default: `-60.0 dB`)
* **What it does:** The attenuation floor applied to silent / non-vocal sections.
  * `-60.0 dB` drops background bleed by 60 dB (inaudible in a mix).
  * `-90.0 dB` creates complete digital black (zero sound).

### `min_vocal_duration`
* **Range:** `0.02 s` to `0.30 s` (Default: `0.08 s`)
* **What it does:** Minimum length of vocal activity to trigger the gate. Prevents short drum clicks or snare leakage from opening the gate.

#### 🎧 Fine-Tuning Voice Examples:
* **Problem: The singer's quiet whispers or trailing breath sounds at the end of words are being cut off (choppy voice).**
  * *Solution:* Lower `gate_threshold_db` to `-65.0 dB` and set `gate_floor_db` to `-45.0 dB` for a softer, more gradual gating curve.
* **Problem: Drum snare hits in an acoustic recording are leaking through during pauses.**
  * *Solution:* Raise `gate_threshold_db` to `-48.0 dB` and increase `min_vocal_duration` to `0.12 s`.

---

## 4. Spectral Denoising & Multi-Band Filtering

Neural separation can occasionally leave residual "music bleed" (e.g., high hi-hat bleed or low synth hum) across the frequency spectrum. VocalPro uses spectral gating noise reduction.

### `enable_spectral_denoise` & `denoise_strength`
* **Range:** `0.00` to `1.00` (Default: `0.55`)
* **What it does:** Applies short-time Fourier transform (STFT) spectral subtraction to eliminate stationary and residual bleed from the vocal stem.

#### 🎧 Audio Impact:
* **`0.00` to `0.20` (Gentle):** Preserves 100% of the natural vocal harmonics and room ambiance. Slight instrumental bleed may remain.
* **`0.40` to `0.60` (Balanced Studio Standard):** Clean acapella with zero perceptible music bleed while keeping the vocal timbre intact.
* **`> 0.75` (Aggressive):** Extreme cleaning. Caution: setting this too high causes "underwater" swirling artifacts and loses the subtle breath textures of the voice.

---

### `enable_multiband_denoise` (Multi-Band Spectral Split)
* **Type:** Boolean (Default: `false`, Recommended for Bass-Heavy Music)
* **Split Frequencies (`denoise_band_split_hz`):** `[250.0, 6000.0]` (Sub/Bass, Mid Body, High Air)
* **Strengths:**
  * `denoise_strength_low`: `0.35` (Cleans 808s, kick drums, and low-frequency rumble)
  * `denoise_strength_mid`: `0.10` (Keeps the core human vocal body untouched and warm)
  * `denoise_strength_high`: `0.25` (Removes cymbal wash and hi-hat sizzle)

#### 🎧 Why Multi-Band Denoising is Powerful:
Human voice fundamentals sit primarily in the **250 Hz – 4 kHz** range. Standard full-band denoising treats all frequencies equally, which can thin out the singer's voice.  
Multi-Band denoising allows you to **aggressively eliminate bass and drum rumble (< 250 Hz)** while leaving the **vocal mid-range pristine and uncompressed**.

---

## 5. High-Frequency Air & Clarity Restoration (HF Restore)

All AI stem separation algorithms and spectral gates naturally attenuate ultra-high frequencies (> 8 kHz), which can make isolated vocals sound slightly "veiled" or "muffled".

### `enable_hf_restore`
* **Type:** Boolean (Default: `true`)
* **`hf_boost_db`:** `0.0 dB` to `6.0 dB` (Default: `3.0 dB`)
* **Crossover Frequency:** `8,000 Hz`

```
Amplitude (dB)
    │                                  ┌──── +3.0 dB Shelf Boost
    │                                 ╱
    │  [Vocal Body: Flat 0 dB]       ╱
 0dB├───────────────────────────────┘
    │
    └──────────────┬───────────────────┬────────▶ Frequency (Hz)
                  250 Hz             8,000 Hz
```

#### 🎧 Audio Impact:
* **With HF Restore Disabled (`0 dB`):** Acapella can sound dry and slightly dark, as if recorded behind a thick pop filter.
* **With HF Restore Active (`+3.0 dB`):** Restores vocal "sheen", crisp sibilance (the crisp 's', 't', and 'ch' sounds), and modern studio "air" without introducing harshness.

---

## 6. Harmonic-Percussive SFX Separation (HPSS)

### `enable_sfx_separation`
* **Type:** Boolean (Default: `false`)
* **What it does:** Splits the non-vocal audio into two distinct sub-tracks:
  1. **Harmonic (Tonal Music):** Guitars, synths, strings, keyboard chords, basslines.
  2. **Percussive (SFX & Transients):** Drums, beatbox, gunshots, explosions, film sound effects, and Foley.
* **`sfx_separation_margin_db`:** `5.0 dB` (Higher margin enforces stricter separation).

#### 🎧 Practical Use Cases:
* **Remixers / Producers:** Extract the pure synth and chord progressions of a song without the drums, allowing you to drop in your own custom drum beats.
* **Content Creators & Streamers:** Clean dialogue by stripping video game gunshots and explosions onto a separate track.

---

## 7. Hardware Calibration, Memory Caps & Speed Tuning

VocalPro dynamically balances CPU, GPU, and RAM to prevent crashes and maximize throughput.

| Setting | Default | Recommended Value | Impact on Application |
| :--- | :--- | :--- | :--- |
| `hardware_auto_optimize` | `true` | `true` | Auto-detects RAM/VRAM and configures optimal batching. |
| `max_concurrent_jobs` | `1` | `1` (or `2` if GPU ≥ 8GB VRAM) | Number of songs processed in parallel. Setting to 1 prevents memory exhaustion. |
| `fp16_inference` | `false` | `true` (if NVIDIA RTX GPU) | Uses half-precision FP16 tensors. **Cuts separation time by ~40%** with zero audible quality loss on modern GPUs. |
| `keep_model_warm_in_memory` | `true` | `true` | Keeps Demucs loaded in RAM so subsequent batch songs start instantly without a 3-second warm-up delay. |
| `audio_bitrate` | `"320k"` | `"320k"` | Quality for MP3/AAC exports (uses CBR for maximum compatibility). |
| `output_format` | `"wav"` | `"wav"` (or `"flac"`) | Lossless uncompressed 24-bit / 16-bit PCM for professional DAW workflows. |

---

## 8. Turnkey Preset Recipes for Common Scenarios

You can instantly configure VocalPro for specific use cases using these recommended recipes:

### 🎤 Preset 1: "Crystal-Clear Studio Vocals" (Sampling & Acapellas)
* **Goal:** Maximum vocal clarity, zero instrumental bleed, pristine high-end.
* **Settings:**
  * `model_name`: `"htdemucs_ft"`
  * `shifts`: `2`
  * `overlap`: `0.35`
  * `enable_vocal_gate`: `true`
  * `gate_threshold_db`: `-55.0`
  * `enable_spectral_denoise`: `true`
  * `denoise_strength`: `0.60`
  * `enable_hf_restore`: `true`
  * `hf_boost_db`: `3.5`

---

### 🎸 Preset 2: "Acoustic Band / Live Performance" (6-Stem Separation)
* **Goal:** Isolate lead vocals, guitar, and piano into separate stems for acoustic covers or karaoke.
* **Settings:**
  * `model_name`: `"htdemucs_6s"`
  * `output_all_stems`: `true`
  * `shifts`: `1`
  * `overlap`: `0.25`
  * `enable_vocal_gate`: `true`
  * `gate_threshold_db`: `-52.0`
  * `enable_spectral_denoise`: `true`
  * `denoise_strength`: `0.45` (gentle to preserve acoustic guitar bleed warmth)

---

### ⚡ Preset 3: "Fast DJ / Party Mashup Prep" (High Speed)
* **Goal:** Process 20 tracks in minutes for live DJing or remix stems.
* **Settings:**
  * `model_name`: `"htdemucs"`
  * `shifts`: `0`
  * `overlap`: `0.15`
  * `fp16_inference`: `true`
  * `enable_spectral_denoise`: `true`
  * `denoise_strength`: `0.50`
  * `keep_model_warm_in_memory`: `true`

---

### 🎙️ Preset 4: "Podcast / Dialogue & SFX Cleaner"
* **Goal:** Extract clean speech from noisy background video, music, or game audio.
* **Settings:**
  * `model_name`: `"htdemucs"`
  * `enable_vocal_gate`: `true`
  * `gate_threshold_db`: `-50.0`
  * `gate_floor_db`: `-65.0`
  * `enable_multiband_denoise`: `true`
  * `denoise_strength_low`: `0.70` (strips air conditioning hum and traffic rumble)
  * `denoise_strength_mid`: `0.15`
  * `denoise_strength_high`: `0.40`
  * `enable_sfx_separation`: `true`

---

## 🛠️ How to Edit Settings in VocalPro

1. **Inside the App UI:** Click the **Settings (⚙️)** icon in the navigation bar to access sliders, toggles, and dropdowns for all options with instant preview.
2. **Export / Import Configurations:** In the Settings panel, click **Export Settings JSON** to save your customized profile (e.g., `MyStudioVocalPreset.json`) and share it across devices.
3. **Emergency Reset:** Click **Reset to Defaults** at any time to restore factory recommended settings.
