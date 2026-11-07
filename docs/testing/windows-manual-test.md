# VocalPro v3.0.0 — Windows 10/11 & GPU Manual Verification Pack

Per **Evidence & Honesty Rule #4** of the Verification & Hardening Pass Mandate, any behavior that requires a physical Windows 10/11 desktop session, a physical WASAPI hardware audio output device, OS Explorer drag-and-drop, or a physical NVIDIA CUDA / AMD / Intel GPU is marked `UNVERIFIED` in the automated Linux VM test matrix and documented here with exact step-by-step verification procedures.

---

## 1. Prerequisites on Your Windows 10/11 Machine

```powershell
git clone https://github.com/lam3y35/vocal-pro-rebuild.git
cd vocal-pro-rebuild
npm install
```

Ensure Python 3.11+ with `torch`, `torchaudio`, `demucs`, `numpy`, `scipy`, `soundfile`, `librosa`, `noisereduce`, `resampy`, `jsonschema` is available (or in `.venv\Scripts\python.exe`), and Rust stable toolchain (`cargo`) is installed.

To launch the native Tauri v2 desktop window:
```powershell
npm run tauri dev
```
Or build the release NSIS installer:
```powershell
npm run tauri build
```

---

## 2. Step-by-Step Verification Checklist

### Test W-01: Native Windows Tauri v2 Desktop Window, Always-on-Top & System Tray (`OS-03`, `OS-04`)
- **Why `UNVERIFIED` in VM:** The CI/VM environment is a headless Linux container without a Windows Explorer shell or Windows system tray (`Shell_NotifyIconW`).
- **Steps:**
  1. Launch VocalPro v3 (`npm run tauri dev`).
  2. Navigate to **Settings -> Storage Cache, OS Integration, FFmpeg & Diagnostics**.
  3. Toggle **Window Always on Top** ON.
  4. Click another maximized application window (e.g., Notepad or Explorer).
  5. Toggle **Minimize to System Tray** ON and minimize/close the window.
- **Expected Result:**
  - When **Window Always on Top** is ON, the VocalPro window remains above other normal desktop windows.
  - When **Minimize to System Tray** is ON, VocalPro minimizes to the Windows notification area tray icon and restores when clicked.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________

---

### Test W-02: Windows Registry File Associations & Desktop `.lnk` Shortcut (`OS-01`, `OS-02`)
- **Why `UNVERIFIED` in VM:** `HKCU\Software\Classes` (`reg.exe`) and `WScript.Shell` (`cscript.exe //NoLogo CreateShortcut.vbs`) only execute their native OS paths on `cfg(target_os = "windows")`.
- **Steps:**
  1. In **Settings**, click **Register File Associations (.mp3/.wav/.mp4)**.
  2. Open PowerShell and run:
     ```powershell
     reg query "HKCU\Software\Classes\VocalPro.MediaFile\shell\open\command"
     reg query "HKCU\Software\Classes\.mp3"
     ```
  3. In **Settings**, click **Create Desktop Shortcut**.
  4. Check `$env:USERPROFILE\Desktop\VocalPro.lnk`.
- **Expected Result:**
  - `HKCU\Software\Classes\VocalPro.MediaFile` and `.mp3`, `.wav`, `.flac`, `.ogg`, `.mp4`, `.mkv`, `.avi`, `.mov` keys exist and point to the VocalPro executable.
  - `VocalPro.lnk` appears on the Windows Desktop and launches VocalPro when double-clicked.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________

---

### Test W-03: Windows Explorer Native Drag-and-Drop (`IN-01`, `UI-02`)
- **Why `UNVERIFIED` in VM:** Headless Linux Chromium tests file path addition via input/store, not native Windows OLE `IDropTarget` drag-and-drop from `explorer.exe`.
- **Steps:**
  1. Open Windows Explorer containing an `.mp3`, `.wav`, and `.mp4` file.
  2. Drag the files from Windows Explorer and drop them onto the **Input Audio & Video Queue** card on the **AI Separation** screen.
- **Expected Result:**
  - All dropped files appear immediately in the Input Queue with `AUDIO` / `VIDEO` badges, and the 8,000-point input waveform preview renders in `< 300 ms`.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________

---

### Test W-04: Real WASAPI Hardware Audio Output & Real-Time 6-Stem Mixer (`MIX-01`..`MIX-04`)
- **Why `UNVERIFIED` in VM:** The Linux VM has no physical soundcard or speakers attached; automated tests verify `LiveStemMixer::render_interleaved_frames` in memory (`0.088 ms` render latency, `30.28 MiB` streaming buffer).
- **Steps:**
  1. Run a separation job with model **HTDemucs 6-Stem (`htdemucs_6s`)** on a real song.
  2. Open **Outputs & Mixer**, select the separated track, and click **Play** (or press `Space`).
  3. While audio plays through your headphones/speakers, drag the **Vocals**, **Drums**, **Bass**, **Guitar**, **Piano**, and **Other** gain sliders (`0%`–`200%`) and toggle **Mute (`M`)** and **Solo (`S`)**.
- **Expected Result:**
  - Audio plays smoothly without clicks, pops, or underruns.
  - Gain, Mute, and Solo changes are heard instantaneously (`< 15 ms`) without pausing playback or spawning `ffmpeg`.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________

---

### Test W-05: Physical NVIDIA CUDA GPU Detection, VRAM Auto-Tuning & OOM Fallback (`SYS-02`, `DSP-17`)
- **Why `UNVERIFIED` in VM:** The Linux VM is a CPU-only Intel Xeon instance (`cuda_available = false`); automated tests exercise the 6 hardware tiers via `classify_hardware_spec` simulation.
- **Steps:**
  1. On a Windows PC with an NVIDIA GPU, open **Settings**.
  2. Inspect the **Hardware Intelligence & Multi-Process Device Optimizer** banner.
  3. Click **Re-Detect & Calibrate (`<=30s`)**.
  4. Run a separation job with **Device = Auto (CUDA)** and verify GPU utilization in Windows Task Manager (`Compute_0` / `CUDA`).
  5. Optional: Toggle **CUDA FP16 Half-Precision Inference (Opt-In Only)** ON and compare speed vs default FP32.
- **Expected Result:**
  - GPU model name and VRAM MB are displayed accurately, and tier is classified as `ultra_gpu` (`>=12 GB`), `high_gpu` (`6–11 GB`), or `entry_gpu` (`4–5 GB`).
  - Default `Auto`, `Balanced`, and `Max Quality` profiles keep `FP16 = Disabled (Bit-Exact FP32)` unless explicitly opted in.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________

---

### Test W-06: Windows Real-Window Cold Start Time
- **Why `UNVERIFIED` in VM:** The Linux VM measured `742 ms` DOMContentLoaded + networkidle in headless Chromium on Linux over `vite preview` with mocked IPC. Real WebView2 initialization + native window creation + SQLite load on physical Windows 10/11 requires a real Windows desktop.
- **Steps:**
  1. Close VocalPro completely (ensure no background `vocalpro.exe` in Task Manager).
  2. Launch VocalPro from Desktop shortcut or Start Menu.
  3. Time from launch until the main interactive UI appears.
- **Expected Result:**
  - Window appears and becomes interactive in `< 1.5 s` on SSD.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Time measured: _______ s

---

### Test W-07: Windows NSIS Installer Installation and Clean Uninstallation
- **Why `UNVERIFIED` in VM:** NSIS installer (`.exe`) execution, registry writes, and uninstallation require an interactive Windows desktop.
- **Steps:**
  1. Download the Windows NSIS installer artifact (`vocalpro-windows-x86_64`) from the GitHub Actions CI run.
  2. Run the installer (per-user install to `%LOCALAPPDATA%\Programs\VocalPro`).
  3. Verify Start Menu shortcut and Desktop shortcut are created.
  4. Run Windows **Settings -> Installed apps -> VocalPro -> Uninstall**.
  5. Check `%LOCALAPPDATA%\Programs\VocalPro` and Desktop shortcut.
- **Expected Result:**
  - Installer completes without admin prompt (currentUser mode).
  - Uninstaller removes application binaries, shortcuts, and registry associations cleanly.
- **Pass / Fail:** `[ ] PASS  [ ] FAIL` — Notes: ______________________
