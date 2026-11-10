# VocalPro v3 — Master Reference & Fine-Tuning Guide

> **Target Audience:** Audio Producers, Sound Engineers, DJs, Content Creators, Vocalists, and Developers.  
> **Purpose:** Comprehensive, detailed reference explaining every dashboard card, button, technical metric, separation parameter, and advanced setting in VocalPro v3, accompanied by before/after audio examples and tuning recommendations.

---

## 📑 Table of Contents
1. [Dashboard & Studio Status Bar](#1-dashboard--studio-status-bar)
   - [Setup Wizard (First-Run Hardware & Studio Setup)](#setup-wizard)
   - [N4: 0 Listening Ports Explained](#n4-0-listening-ports-explained)
   - [N5: < 500ms Cooperative Job Cancellation](#n5--500ms-cooperative-job-cancellation)
   - [Auto-Tune for Hardware Button](#auto-tune-for-hardware-button)
   - [Python AI Worker Pool & "Restart Python AI Worker"](#python-ai-worker-pool--restart-python-ai-worker)
2. [Waveform Preview & Interactive Timeline](#2-waveform-preview--interactive-timeline)
   - [Native Rust 8,000-Point Waveform Preview](#native-rust-8000-point-waveform-preview)
   - [The Interactive Waveform Scrubber Line](#the-interactive-waveform-scrubber-line)
3. [Separation Workstation Parameters (With Higher vs. Lower Examples)](#3-separation-workstation-parameters)
   - [Output Mode (Vocals, Instrumental, All Stems, Karaoke)](#output-mode)
   - [Audio Output Format & Bit Depth](#audio-output-format--bit-depth)
   - [Inference Device (CUDA vs. AVX2 CPU)](#inference-device)
   - [Video Output Mode (Audio Only, Clean Vocals Video, Instrumental Video, Both)](#video-output-mode)
   - [Random Shifts (Test-Time Augmentation)](#random-shifts-tta)
   - [Segment Duration (Chunk Length in Seconds)](#segment-duration)
   - [Overlap Ratio (Sliding Window Crossfade)](#overlap-ratio)
   - [Parallel Worker Slots (Multi-Process Concurrency)](#parallel-worker-slots)
4. [Vocal Post-Processing & DSP Chain](#4-vocal-post-processing--dsp-chain)
   - [VAD Voice Activity Gate](#vad-voice-activity-gate)
   - [Full-Band & Multi-Band Spectral Denoise](#spectral-denoise)
   - [High-Frequency Air & Clarity Restoration (HF Restore)](#high-frequency-air-restore)
   - [Harmonic-Percussive SFX Separation (HPSS)](#hpss-sfx-separation)
5. [Turnkey Presets & Real-World Voice Examples](#5-turnkey-presets--real-world-voice-examples)
6. [Advanced Settings Panel Explained](#6-advanced-settings-panel-explained)
   - [Conflict Policy & Naming Templates](#conflict-policy--naming-templates)
   - [Cache Management & Folder Preservation](#cache-management)
   - [Accessibility, UI Scale & Themes](#accessibility-ui-scale--themes)
   - [OS Integration (Shortcuts & File Associations)](#os-integration)
7. [Export Diagnostic Log Bundle](#7-export-diagnostic-log-bundle)

---

## 1. Dashboard & Studio Status Bar

### Setup Wizard
When you open VocalPro or click **Setup Wizard** in the top navigation bar, the setup wizard guides you through optimizing your machine for AI stem separation:
1. **Hardware Tier Detection:** Probes your physical CPU cores, RAM size, and graphics card. It identifies whether you have an NVIDIA GPU (CUDA), Apple Silicon (MPS), or an AVX2-capable CPU.
2. **Performance Profile Allocation:** Selects whether your computer should operate in **Eco** (low RAM, 1 worker), **Balanced** (standard multi-core), or **Max Quality** (multi-pass TTA on GPU).
3. **Storage Location Setup:** Lets you verify or change where your separated songs and stems are saved.
4. **Worker Initialization:** Performs an internal handshake with the PyTorch worker pool to verify that neural weights load cleanly without crashing.

---

### N4: 0 Listening Ports Explained
In older AI tools (and Python web interfaces like Gradio, Streamlit, or Flask), the application runs a local web server listening on ports like `http://localhost:8000` or `127.0.0.1:5000`. This approach creates major real-world problems:
- **Port Conflicts:** If another program or browser tab is using that port, the app fails to start with error `WinError 10055` or `EADDRINUSE`.
- **Firewall & Antivirus Blocks:** Windows Defender and third-party firewalls frequently block local TCP servers or show annoying security alerts.
- **Latency & Overhead:** Serialization over HTTP/WebSocket sockets adds latency and memory overhead.

**How VocalPro v3 Solves This:**  
VocalPro v3 runs on **0 Listening Ports**. The React desktop interface communicates directly with the native Rust Core and the Python AI Worker pool using operating system standard I/O streams (**stdio JSON-Lines IPC**).  
- No TCP ports are opened.
- No network traffic is transmitted.
- 100% private, offline, and completely immune to socket or firewall conflicts.

---

### N5: < 500ms Cooperative Job Cancellation
In older neural separation applications, clicking "Cancel" either did nothing for 30–60 seconds while the GPU finished a huge computation batch, or it forcefully terminated the Python process, crashing the application.

**How VocalPro v3 Solves This:**  
VocalPro uses **cooperative token-based cancellation**:
- The Demucs inference loop slices audio into sub-second evaluation chunks.
- Between every chunk, the worker checks an atomic cancellation token received over stdio.
- When you click **Cancel** (or press the `Escape` key), the worker immediately halts tensor computation, flushes VRAM/RAM buffers, and resets to a ready state in **under 500 milliseconds (< 500ms)** without needing to restart the app.

---

### Auto-Tune for Hardware Button
Located on the Studio Overview dashboard, the **Auto-Tune for Hardware** button runs an automated performance audit of your computer:
1. It queries physical CPU cores, logical threads, available RAM, and GPU VRAM.
2. It tests your temp disk write throughput to ensure smooth multi-stem saving.
3. It automatically sets the optimal parameters:
   - Sets **Parallel Workers** (e.g., 1 for 8 GB RAM, 2 for 16 GB, 4 for 32+ GB).
   - Sets **Segment Duration** (6.0s on CPU, 7.8s on CUDA).
   - Sets **Inference Precision** (FP32 on CPU, FP16 on Tensor Core GPUs).
4. It displays an instant notification banner showing the exact settings applied (e.g., `Auto-tuned for hardware: CUDA • 2 parallel workers • segment=7.8s`).

---

### Python AI Worker Pool & "Restart Python AI Worker"
- **What is the Worker Pool?**  
  To keep the desktop interface buttery smooth at 60 FPS, all heavy neural network computation happens in isolated background processes called **Workers**.
- **What does the "Restart Python AI Worker" button do?**  
  If a corrupted audio file, an out-of-memory condition, or an unexpected OS driver error ever freezes the background AI process, clicking **Restart Python AI Worker** immediately terminates any hanging worker process and spawns a fresh, clean PyTorch instance in under 50 milliseconds. You never have to restart the whole application or lose your open workspace.

---

## 2. Waveform Preview & Interactive Timeline

### Native Rust 8,000-Point Waveform Preview
When you add an audio file, VocalPro instantly generates an 8,000-point visual waveform preview.
- **Why Native Rust?**  
  Instead of loading the entire heavy audio file into Python or the browser's JavaScript memory, a specialized Rust DSP engine (using the `symphonia` audio library) reads the file headers and extracts 8,000 min/max amplitude peaks in **under 50 milliseconds**.
- **What do the peaks mean?**  
  - Taller vertical bars represent louder musical sections (choruses, drops, drum beats).
  - Thinner horizontal bars represent quieter sections, speech pauses, or acoustic intros.

---

### The Interactive Waveform Scrubber Line
Inside the waveform display, you will notice a vertical line that moves as audio plays:
- **This is the Interactive Playhead / Scrubber.**
- **How to use it:** You can click or drag anywhere along the waveform to scrub through the audio and immediately seek to that exact time in the song.
- When listening to separated stems in the Stem Mixer, moving this scrubber jumps all stems (vocals, drums, bass, instruments) simultaneously in lockstep.

---

## 3. Separation Workstation Parameters

This section explains every option available on the Separation Workstation and how setting each parameter **higher or lower** directly impacts the sound and app speed.

---

### Output Mode
Controls which stems are written to disk:
1. **Vocals Only:** Extracts only the clean lead/backing vocal stem and discards other stems. Ideal when you only need acapellas for remixing or vocal analysis.
2. **Instrumental / Backing Track:** Extracts the complete backing track without vocals (instant karaoke).
3. **All Stems (Recommended for Producers):** Saves every isolated track: Vocals, Drums, Bass, and Other (plus Piano and Guitar if using the 6-stem model).
4. **Karaoke Mode:** Generates a lead vocal track and an accompaniment track with an optional subtle guide vocal.

---

### Audio Output Format & Bit Depth
* **`WAV` (16-bit / 24-bit / 32-bit Float PCM):**  
  - *When to use:* Studio production, mixing, and mastering in DAWs (Ableton, FL Studio, Logic, Pro Tools).  
  - *Quality:* 100% lossless uncompressed.  
* **`FLAC` (Free Lossless Audio Codec):**  
  - *When to use:* Archiving stems where you want bit-perfect studio quality at ~50% the file size of WAV.  
* **`MP3` (LAME CBR 128k – 320k):**  
  - *When to use:* Quick previews, sharing via chat apps, or mobile storage. Always use **320 kbps** for maximum high-frequency clarity.

---

### Inference Device
* **`CUDA` (NVIDIA Graphics Card):**  
  Uses hardware Tensor Cores. Runs 3x to 10x faster than CPU.
* **`CPU` (Multi-Threaded AVX2 / Apple Silicon):**  
  Uses high-performance vectorized CPU SIMD instructions. Flawless audio quality; recommended if your computer does not have an NVIDIA GPU.

---

### Video Output Mode
When you separate a video file (`.mp4`, `.mkv`, `.avi`, `.mov`), VocalPro can automatically remix the video:
* **Audio Only:** Extracts the soundtrack and outputs standard audio files.
* **Clean Vocals Video:** Replaces the video's original audio with the isolated speech/vocal stem (perfect for interviews and subtitles).
* **Instrumental Video:** Replaces the video's audio with the instrumental backing track (ideal for video karaoke).
* **Both:** Produces two synchronized video copies.

---

### Random Shifts (TTA)
* **Parameter Range:** `0` to `4` (Default: `1`)
* **What it does:** Test-Time Augmentation (TTA). The engine shifts the audio waveform randomly by a few samples, runs inference on each shifted copy, shifts them back, and averages the spectrograms.
* **Impact of Changing:**
  - **Higher (`shifts = 2` to `4`):**  
    * *Audio Result:* Eliminates all phase roughness, metallic flutter, and high-frequency "underwater" artifacts. Vocals sound warm, natural, and open.  
    * *Speed Trade-off:* Each shift adds a full inference pass (e.g., `shifts = 2` takes 3x the processing time of `shifts = 0`).  
  - **Lower (`shifts = 0`):**  
    * *Audio Result:* Fastest processing speed (1x time). However, you may hear subtle robotic or metallic phase artifacts on sustained vocal vowels.  
    * *Best for:* Quick draft previews.

---

### Segment Duration
* **Parameter Range:** `4.0` seconds to `10.0` seconds (Default: `6.0s` CPU / `7.8s` GPU)
* **What it does:** The temporal window size processed by the neural network in each chunk.
* **Impact of Changing:**
  - **Higher (`7.8s` to `10.0s`):**  
    * *Audio Result:* The AI sees more musical context, resulting in cleaner separation of slow vocal vibrato, long reverb tails, and deep sub-bass notes.  
    * *Resource Trade-off:* Requires more RAM and GPU VRAM (up to 4 GB VRAM).  
  - **Lower (`4.0s` to `5.0s`):**  
    * *Audio Result:* Slightly less bass coherency, but still very clean vocals.  
    * *Resource Advantage:* Keeps VRAM under 1.8 GB, preventing Out-Of-Memory (OOM) crashes on budget laptops.

---

### Overlap Ratio
* **Parameter Range:** `0.10` (10%) to `0.50` (50%) (Default: `0.25` / 25%)
* **What it does:** How much adjacent 6-second segments overlap when passed through the AI. Overlaps are crossfaded using smooth cosine window curves.
* **Impact of Changing:**
  - **Higher (`0.35` to `0.50`):**  
    * *Audio Result:* 100% transparent transitions. Eliminates volume dips, clicks, or popping noises at the boundaries between segments.  
    * *Trade-off:* Takes ~30% longer to process.  
  - **Lower (`0.10` to `0.15`):**  
    * *Audio Result:* Processing is ~25% faster, but on quiet vocals or ambient songs, you may hear faint periodic volume flutter every few seconds.

---

### Parallel Worker Slots
* **Parameter Range:** `1` to `4` concurrent worker processes (Default: `2`)
* **What it does:** How many songs are processed at the exact same time.
* **Impact of Changing:**
  - **Higher (`3` to `4` workers):**  
    * *Performance:* If you add a batch of 10 songs, 4 songs will separate simultaneously, cutting total batch time in half.  
    * *Hardware Requirement:* Requires at least 16 GB RAM and 8+ CPU cores.  
  - **Lower (`1` worker):**  
    * *Performance:* Processes songs one by one in sequence.  
    * *Best for:* Machines with 8 GB RAM or when you want your PC to stay cool and quiet while working in other apps.

---

## 4. Vocal Post-Processing & DSP Chain

After the neural network separates the raw stem, VocalPro runs an in-memory 32-bit floating-point DSP cleaning chain:

```
Raw AI Vocal ──▶ [VAD Noise Gate] ──▶ [Spectral Denoise] ──▶ [HF Air Restore] ──▶ Pristine Acapella
```

### VAD Voice Activity Gate
* **`enable_vocal_gate` (`true` / `false`):** Mutes background bleed when the singer is silent between lyrics.
* **`gate_threshold_db` (`-70 dB` to `-30 dB`):** Volume sensitivity to detect voice.
  - *Higher (`-45 dB`):* Stricter gate. Cuts out quiet breaths and snare drum bleed, but might accidentally chop off the end of quiet whisper words.
  - *Lower (`-65 dB`):* Gentle gate. Preserves every breath and subtle vocal tail.
* **`gate_floor_db` (`-90 dB` to `-30 dB`):** Volume floor during silence. `-60 dB` reduces bleed to inaudible levels; `-90 dB` produces absolute digital silence.

---

### Spectral Denoise
* **`enable_spectral_denoise` (`true` / `false`):** Removes residual background instrument hum or cymbal sizzle using spectral subtraction.
* **`denoise_strength` (`0.00` to `1.00`, Default: `0.55`):**
  - *Higher (`0.75` – `0.90`):* Completely strips any remaining instrumental bleed, but setting it too high can make the voice sound "hollow" or "underwater".
  - *Lower (`0.20` – `0.40`):* Preserves 100% of vocal warmth and room reverb with minimal filtering.
* **Multi-Band Denoising (`enable_multiband_denoise`):**  
  Splits the frequency spectrum into 3 independent bands (Low < 250 Hz, Mid 250 Hz – 6 kHz, High > 6 kHz). This allows aggressive cleaning of low bass rumble without touching the vocal mid-range.

---

### High-Frequency Air Restore
* **`enable_hf_restore` (`true` / `false`):**
  Neural network separation naturally softens ultra-high frequencies (> 8 kHz). When enabled, this applies a high-shelf boost (`+3.0 dB`) to restore studio "sheen", crisp consonants ('s', 't', 'ch'), and natural vocal air.

---

### HPSS SFX Separation
* **`enable_sfx_separation` (`true` / `false`):**
  Harmonic-Percussive Source Separation splits background audio into:
  1. *Harmonic:* Tonal music, chords, guitars, and synths.
  2. *Percussive:* Drums, beatbox, gunshots, explosions, and sound effects.  
  Ideal for remixers who want musical chords without drums, or video editors cleaning speech from game SFX.

---

## 5. Turnkey Presets & Real-World Voice Examples

| Preset Name | Best For | Model | Shifts | Overlap | Gate | HF Boost | Sound Character |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Crystal-Clear Studio Vocals** | Sampling, remix acapellas | `htdemucs_ft` | 2 | 0.35 | -55 dB | +3.5 dB | Crisp, airy, zero bleed, polished modern studio sound. |
| **Full 6-Stem Band Split** | Acoustic covers, guitar/piano | `htdemucs_6s` | 1 | 0.25 | -52 dB | +2.0 dB | Isolates piano and guitar onto dedicated tracks. |
| **Cinema Dialogue & SFX Cleaner** | Podcasts, videos, gameplay | `htdemucs` | 1 | 0.25 | -50 dB | +1.5 dB | Removes room rumble and isolates clear speaking voice. |
| **Fast DJ Preview (Eco)** | Rapid mashup prep | `htdemucs` | 0 | 0.15 | -50 dB | 0.0 dB | Maximum processing speed with solid clarity. |

---

## 6. Advanced Settings Panel Explained

Inside the **Settings (⚙️)** panel, toggling **Advanced View** reveals fine-grained engine controls:

### Conflict Policy & Naming Templates
* **Naming Template (`naming_template`):**  
  Determines how output files are named. Uses dynamic tags like `{track}_{stem}` (e.g., `MySong_vocals.wav`).
* **Conflict Policy (`conflict_policy`):**
  - `append_number`: If `MySong_vocals.wav` already exists, creates `MySong_vocals_1.wav`.
  - `overwrite`: Overwrites the old file with the new separation.
  - `skip`: Skips the file if it already exists.

---

### Cache Management & Folder Preservation
* **Preserve Folder Structure:**  
  When separating batches of files inside nested folders, reproduces the same folder tree in your output directory.
* **Max Cache Size (GB):**  
  Limits the disk space used by temporary audio waveforms and downloaded media. Click **Clear Cache** to free disk space instantly.

---

### Accessibility, UI Scale & Themes
* **UI Scale (90%, 100%, 110%, 125%):**  
  Scales all text, buttons, and faders. Great for high-DPI 4K monitors or smaller laptop screens.
* **High Contrast Mode (WCAG AAA):**  
  Increases borders and text contrast for studio environments with dim lighting.
* **Reduced Motion:**  
  Disables waveform animations and smooth transitions to conserve CPU.
* **Always-on-Top:**  
  Pins the VocalPro window above your DAW (FL Studio, Ableton, etc.) so you can drag and drop stems without losing focus.
* **Minimize to Tray:**  
  Hides the window into the Windows System Tray while processing long batches in the background.

---

### OS Integration
* **Register File Associations:**  
  Associates `.mp3`, `.wav`, `.flac`, and `.mp4` files with VocalPro in Windows Explorer so you can right-click any file and select *"Separate with VocalPro"*.
* **Create Desktop Shortcut:**  
  Creates a clean Windows desktop shortcut (`VocalPro.lnk`) pointing to the executable.

---

## 7. Export Diagnostic Log Bundle

Next to the worker health display in Settings is the **Export Diagnostic Log Bundle** button:
* **What does it do?**  
  It compiles a compressed `.zip` archive (`vocalpro_diagnostics.zip`) containing:
  1. `worker_logs.txt`: Recent terminal logs from the Python Demucs worker pool.
  2. `settings.json`: Your active application configuration.
  3. `worker_health.json`: Hardware profile metrics (CPU cores, RAM, GPU VRAM, CUDA capability).
  4. `sqlite_summary.json`: Database integrity status.
* **Privacy Guarantee:**  
  The bundle contains **zero audio files, zero speech data, and zero personal filenames**.
* **When to use it:**  
  If you ever encounter an issue or want to report a bug to the development team, export this bundle and share it. It gives developers all the diagnostic information needed to troubleshoot the issue instantly.

---

## 8. Movie & Cinema Audio Architecture (Long-Form Media & Storage Management)

### 🎬 Cinema Movie Separation Workflow
VocalPro v3 includes an architecture built specifically for full-length feature films and cinema media (1 to 3+ hours):
1. **Audio Extraction Without Video Degradation:**
   The movie audio stream is extracted directly using high-speed decoding into floating-point audio. The video stream remains completely untouched.
2. **Sequential Chunked Processing (Zero OOM Memory Spikes):**
   A 2-hour movie contains over 300 million audio samples. Attempting to pass 2 hours into a neural network in a single tensor would immediately crash with an Out-of-Memory (OOM) error.  
   VocalPro splits the movie audio into sequential chunks (e.g. 10-minute segments) with 5-second overlapping margins (`overlap_seconds=5.0`), processes each chunk through Demucs, and applies smooth equal-power crossfading (`smooth_crossfade_chunks`).
3. **Exact 1:1 Timeline & Period Synchronization:**
   The stitched audio is normalized to the exact frame sample count (`target_samples = mix_ch.shape[1]`), ensuring **sample-accurate lip-sync** across the entire 2-hour duration with zero audio-video drift.
4. **Instant Video Remuxing via Stream-Copy:**
   When remuxing (`-c:v copy -c:a aac -b:a 320k`), the original video stream is bit-copied with zero re-encoding time and **zero visual quality loss**.

---

### 💾 Why Did a 5 MB Song Become 30 MB? (Storage Optimization Guide)
Many users notice that an input 5 MB MP3 file becomes a 30 MB to 45 MB file when processed. Here is the technical explanation and how VocalPro solves it:
- **Uncompressed PCM WAV vs Compressed Audio:**
  Standard CD-quality WAV is uncompressed 16-bit PCM at 1,411 kbps. A 3-minute song in WAV is mathematically ~32 MB! If 24-bit PCM or 32-bit Float is used, it reaches ~48 MB per stem. If 4 stems are saved, that single 5 MB song becomes **130 MB** on your SSD!
- **How to Keep Storage Small Without Losing Quality:**
  - Select **MP3 320 kbps (Studio Quality)** or **AAC / M4A 320 kbps (Cinema Master)** in the Audio Format dropdown.
  - At 320 kbps CBR, human hearing cannot distinguish the audio from raw 24-bit WAV (perceptual studio transparency).
  - Your 5 MB file stays compact (~5 MB to 7 MB), saving over 85% of disk storage!
  - For movies, when exporting **Clean Movie Video Only (`video_only`)**, the output movie file is virtually identical in size to the original movie, and all intermediate WAV chunks and audio stems are purged from disk immediately.

---

### 🎛️ Export Target: Video vs. Audio Only

VocalPro provides 3 distinct export modes:
1. **🎬 Clean Movie Only (`video_only`):**  
   Muxes the isolated clean dialogue (or background music) directly back into your movie container (`.mp4`, `.mkv`, etc.). Automatically unlinks and deletes all temporary audio stems from your hard drive, leaving only your finished movie file.
2. **🎵 Audio Stems Only (`audio_only`):**  
   Extracts and separates the movie soundtrack into isolated Dialogue, Score/Music, and SFX stems as compact audio files (MP3/AAC/FLAC). Skips video creation completely to save processing time and disk space.
3. **🎬+🎵 Both Movie + Audio Stems (`both`):**  
   Creates both the remuxed clean movie file and keeps the separate audio stem files.

---

### 🗑️ Option: Delete Original Input File After Successful Export
Under the Export Target options, you will find:
> **"Delete original input file after successful export"** (`delete_input_file`)

- When enabled, VocalPro verifies that the clean movie/audio file has been written to disk successfully with valid size and frames.
- Once verified, it automatically removes the original bulky input file from disk.
- Ideal for batch processing large 4K movies (e.g. 5 GB to 20 GB files) where keeping both the original movie and the remuxed movie would consume excessive storage.

---

### ⚡ Default Maximum Performance Profile
By default, VocalPro v3 starts in **Maximum Performance Mode ("Max Quality")**:
- **Inference Device:** CUDA GPU acceleration enabled by default (falls back to AVX2 multi-threaded CPU on non-NVIDIA systems).
- **Segment Size:** 7.8 seconds (maximum contextual receptive field for neural transformers).
- **FP16 Acceleration:** Active for high-throughput tensor calculations on modern GPUs.
- **Parallel Workers:** Automatically tuned to maximum concurrent jobs supported by your GPU VRAM and CPU cores.
- **User Control:** If you are running other heavy tasks or on laptop battery, you can easily switch to **Balanced** or **Eco** at any time using the profile switcher in the top navigation bar.
