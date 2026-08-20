<div align="center">

  <img src="vocalpro.ico" width="64" height="64" alt="VocalPro icon"/>

  # 🎤 VocalPro

  **AI-Powered Vocal & Background Music Separation**

  [![Python](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/downloads/)
  [![Flutter](https://img.shields.io/badge/Flutter-3.29+-blue)](https://docs.flutter.dev/get-started/install)
  [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
  [![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)]()
  [![Tests](https://img.shields.io/badge/Tests-446+-brightgreen)]()

  Extract clean vocals, drums, bass, piano, guitar, and more from any audio or video file — **free**, **offline**, and **open source**.

</div>

---

## ✨ Features

| Category | Capabilities |
|----------|-------------|
| **🎤 Vocal Isolation** | Extract studio-quality vocals using 8 AI models (Demucs Hybrid Transformer) |
| **🎬 Video Support** | Process MP4, MKV, AVI, MOV — extract and separate audio tracks |
| **🎛️ Stem Mixer** | 0–200% volume sliders per stem, custom remixing, per-stem export |
| **🎵 BPM & Key Detection** | Automatic tempo and musical key analysis on file load |
| **🔀 Ensemble Mode** | Average results from multiple models for cleaner vocals |
| **🎤 Karaoke Mode** | Export instrumental tracks from all non-vocal stems |
| **📊 Post-Processing** | VAD gating, spectral denoising, adaptive noise profiling |
| **📦 Batch Processing** | Queue multiple files with progress tracking |
| **🌐 URL Loading** | Download and process audio from URLs |
| **🌍 Multi-Language** | 16 locales (English, Spanish, French, Japanese, Chinese, etc.) |
| **⚡ GPU Acceleration** | Auto VRAM tuning, CUDA support |
| **🪟 System Tray** | Minimize-to-tray, always-on-top, persistent window position |

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **Python** | 3.12+ | [Download](https://www.python.org/downloads/) — check "Add to PATH" |
| **FFmpeg** | Any | [Download](https://ffmpeg.org/download.html) — must be on PATH |
| **Flutter SDK** | 3.29+ | [Download](https://docs.flutter.dev/get-started/install) — for building the frontend |

Verify prerequisites are installed:

```bash
python --version    # Should show Python 3.12.x
ffmpeg -version     # Should show FFmpeg version info
flutter --version   # Should show Flutter 3.29+
```

### Installation

```bash
# Clone the repository
git clone https://github.com/lam3y35/vocal-pro.git
cd vocal-pro

# One-click setup (creates venv, installs deps, builds Flutter app)
setup.bat
```

The `setup.bat` script handles everything automatically:
1. Creates a Python virtual environment
2. Installs Python dependencies (PyTorch, Demucs, FastAPI, etc.)
3. Builds the Flutter desktop app

### Running the App

```bash
# Launch the app (starts server + Flutter GUI)
run.bat
```

This will:
- Start the FastAPI backend server on `http://127.0.0.1:8000`
- Build (if needed) and launch the Flutter desktop app
- Auto-stop the server when you close the app

### API-Only Mode

If you want just the backend without the Flutter GUI:

```bash
# Activate virtual environment
venv\Scripts\activate

# Start the API server
python api_server/main.py
```

Then open `http://127.0.0.1:8000/docs` in your browser for the Swagger UI.

---

## 🏗️ Architecture

```
┌─────────────────────┐      HTTP/WebSocket      ┌──────────────────────┐
│   Flutter Frontend  │ ◄──────────────────────► │  FastAPI Python Server│
│  (Windows Desktop)  │   REST API + Progress    │  (AI Backend)        │
└─────────────────────┘                          └──────────────────────┘
                                                          │
                                                    ┌─────▼──────┐
                                                    │  Demucs AI  │
                                                    │   Models    │
                                                    └────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Flutter / Dart (Windows Desktop) |
| **API Server** | FastAPI + Uvicorn |
| **AI Models** | PyTorch + Demucs (8 models) |
| **Audio Analysis** | Librosa, NumPy, SciPy |
| **Post-Processing** | noisereduce, HPSS |
| **Media** | FFmpeg |

### Project Structure

```
vocal-pro/
├── api_server/
│   ├── main.py                 # FastAPI backend (REST + WebSocket)
│   ├── run_server.py           # Server launcher
│   └── requirements.txt        # API dependencies
├── code/
│   ├── separation_engine.py    # Demucs-based audio separation
│   ├── audio_postprocess.py    # VAD, gating, denoising
│   ├── config.py               # Configuration management
│   ├── utils.py                # FFmpeg and audio utilities
│   └── _shared.py              # Shared constants and helpers
├── flutter_app/
│   ├── lib/
│   │   ├── main.dart           # Flutter entry point
│   │   ├── screens/            # UI screens (home, separation, settings, etc.)
│   │   ├── controllers/        # State management (ChangeNotifier)
│   │   ├── services/           # API client + backend service
│   │   ├── widgets/            # Reusable UI components
│   │   └── l10n/               # 16 language translations
│   └── pubspec.yaml            # Flutter dependencies
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── api/                    # API endpoint tests
├── setup.bat                   # One-click installer
├── run.bat                     # App launcher
├── build_dist.bat              # Build distributable ZIP
├── pyproject.toml              # Python project config
└── vocal_pro.html              # Full feature documentation
```

---

## 🧪 Testing

```bash
# Run unit + integration tests (fast, no GPU needed)
venv\Scripts\activate
python -m pytest tests/unit/ tests/integration/ -v

# Run all tests
python -m pytest tests/ -v

# Run Flutter tests
cd flutter_app
flutter test
```

**446+ test cases** covering every module, edge case, and regression.

---

## 🎯 Usage

### Basic Vocal Separation

1. **Launch** the app with `run.bat`
2. **Drag & drop** an audio/video file onto the window (or click Browse)
3. **Select a model** (htdemucs recommended for best quality)
4. **Click Separate** — progress updates in real-time
5. **Download** the cleaned vocals when complete

### Available AI Models

| Model | Quality | Speed | VRAM | Best For |
|-------|---------|-------|------|----------|
| `htdemucs_ft` | ★★★★★ | Slow | ~3.5 GB | Best quality (recommended) |
| `htdemucs` | ★★★★ | Medium | ~2.5 GB | Good balance of speed & quality |
| `htdemucs_6s` | ★★★★ | Medium | ~3 GB | 6 stems (piano + guitar separate) |
| `hdemucs_mmi` | ★★★ | Medium | ~2 GB | Different separation profile |
| `mdx` | ★★★★ | Fast | ~1.5 GB | Good balance |
| `mdx_extra` | ★★★★ | Fast | ~2 GB | More robust |
| `mdx_q` | ★★★ | Very Fast | ~0.5 GB | Low VRAM systems |
| `mdx_extra_q` | ★★★ | Fast | ~1 GB | Low VRAM + better quality |

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Browse files |
| `Ctrl+R` | Start new job |
| `Escape` | Cancel separation |

---

## ⚙️ Configuration

App settings are stored in `%APPDATA%\VocalPro\`:

| File | Description |
|------|-------------|
| `config.json` | User preferences (model, output format, etc.) |
| `separation_history.json` | History of separation runs |
| `download_history.json` | Download history |

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Health check + GPU info |
| `GET` | `/api/config` | Get configuration |
| `POST` | `/api/config` | Update configuration |
| `GET` | `/api/models` | List available AI models |
| `POST` | `/api/upload` | Upload audio/video file |
| `POST` | `/api/separate` | Start separation job |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job details |
| `POST` | `/api/jobs/{id}/cancel` | Cancel a job |
| `GET` | `/api/outputs` | List output files |
| `WS` | `/ws/progress` | Real-time progress stream |

---

## 📦 Building a Distributable

```bash
# Build Flutter app + package into ZIP
build_dist.bat
```

Output: `dist/VocalPro/` (Flutter EXE + Python backend) and `VocalPro-dist.zip` (~13 MB).

---

## 🐛 Troubleshooting

### "Python is not installed or not on PATH"
Install Python 3.12+ from [python.org](https://www.python.org/downloads/) and check **"Add Python to PATH"** during installation.

### "FFmpeg is not on PATH"
Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html) and add it to your system PATH.

### "API server failed to start"
- Check if port 8000 is already in use
- Try starting manually: `venv\Scripts\activate && python api_server/main.py`
- Check the server log: `%TEMP%\vocalpro_server.log`

### "WinError 10055" (Socket exhaustion)
This happens when too many connections accumulate. Reboot your computer, then run `run.bat`.

### "CUDA out of memory"
Use a smaller model (`mdx_q` or `mdx_extra_q`) or reduce the segment size in Advanced settings.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">
  Built with Flutter, FastAPI, PyTorch & Demucs
</div>
