# VocalPro

**AI-powered vocal and background music separation for Windows.**

Remove vocals, drums, bass, and other instruments from any audio or video file using state-of-the-art deep learning (Demucs). Features a modern dark-themed GUI with drag-and-drop support.

![Python](https://img.shields.io/badge/Python-3.12+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)

---

## Quick Start (End Users)

1. Download or clone this repository
2. Double-click **`setup.bat`** — it installs everything automatically
3. After setup, double-click **`run.bat`** to launch the app

That's it. No coding required.

---

## Features

- **Vocal isolation** — Extract clean vocals from any song
- **Stem separation** — Split into vocals, drums, bass, and other
- **Drag & drop** — Drop files directly onto the app window
- **YouTube support** — Paste a URL to separate audio directly
- **Multiple formats** — WAV, MP3, FLAC, OGG, and video formats
- **Advanced post-processing** — VAD gating, spectral denoising, SFX separation
- **Dark mode UI** — Modern purple/dark theme with waveforms
- **History tracking** — Browse and re-process previous separations

---

## For Developers

### Prerequisites

- **Python 3.12+** ([download](https://www.python.org/downloads/))
- **FFmpeg** ([download](https://ffmpeg.org/download.html)) — must be on PATH
- **CUDA-capable GPU** (recommended) — CPU works but is significantly slower

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/vocal-pro.git
cd vocal-pro

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Run the app
python code\gui_app.py
```

### Running Tests

```bash
python -m pytest code/test_all.py -x -q
```

---

## Project Structure

```
vocal-pro/
├── code/
│   ├── __init__.py              # Package init
│   ├── _shared.py               # Shared constants, colors, widgets
│   ├── audio_postprocess.py     # VAD, gating, denoising, HPSS
│   ├── config.py                # Configuration management
│   ├── gui_app.py               # Main GUI application (entry point)
│   ├── history_mixin.py         # History panel mixin
│   ├── separation_engine.py     # Demucs-based audio separation
│   ├── stem_mixer_mixin.py      # Stem mixing controls mixin
│   ├── url_handler_mixin.py     # YouTube/URL handling mixin
│   ├── utils.py                 # FFmpeg and audio utilities
│   ├── waveform_mixin.py        # Waveform display mixin
│   ├── conftest.py              # Pytest fixtures
│   └── test_all.py              # Test suite (1000+ tests)
├── requirements.txt             # Python dependencies
├── theme.json                   # CustomTkinter theme
├── vocalpro.ico                 # Application icon
├── gui_app.spec                 # PyInstaller build config
├── setup.bat                    # One-click Windows installer
├── run.bat                      # Quick launcher
├── build_dist.bat               # Build distributable zip
├── .gitignore
├── LICENSE                      # MIT
└── README.md
```

---

## Building a Standalone Executable

```bash
# Install PyInstaller (already in requirements)
pip install pyinstaller

# Build
pyinstaller gui_app.spec

# Output is in dist/VocalPro/
```

---

## Configuration

App settings are stored in `%APPDATA%\VocalPro\` on Windows:

| File | Description |
|------|-------------|
| `config.json` | User preferences (model, output format, etc.) |
| `separation_history.json` | History of separation runs |
| `download_history.json` | YouTube download history |
| `presets/` | Saved preset configurations |

---

## Tech Stack

- **GUI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (dark theme)
- **AI Model**: [Demucs](https://github.com/facebookresearch/demucs) (Meta Research)
- **Audio**: librosa, soundfile, sounddevice, noisereduce
- **Build**: PyInstaller

---

## License

[MIT](LICENSE)
