"""VocalPro – Modern dark-themed GUI for vocal/background music separation."""

from __future__ import annotations

import gc
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from datetime import datetime
from tkinter import filedialog
from typing import TYPE_CHECKING, Optional

import librosa
import numpy as np
import sounddevice as sd
import soundfile as sf

if TYPE_CHECKING:
    from code.separation_engine import SeparationEngine
from urllib.parse import urlparse

import customtkinter as ctk

from code._shared import (
    _ACCENT, _ACCENT_H, _BG, _BORDER, _CARD_BG, _CARD_TOP, _ERROR,
    _HISTORY_FILE, _PRESETS_DIR, _SEP_HISTORY_FILE,
    _SETTINGS_KEYS, _SUCCESS, _SUPPORTED_EXTS, _TEXT, _TEXT_DIM, _WARNING,
    AccentButton, Card, create_desktop_shortcut, DangerButton, GhostButton,
    DropZone, StatusBadge,
)
from code.config import load_config, save_config, DEFAULT_CONFIG
from code.utils import check_ffmpeg

from code.history_mixin import HistoryMixin
from code.stem_mixer_mixin import StemMixerMixin
from code.url_handler_mixin import URLHandlerMixin
from code.waveform_mixin import WaveformMixin

# Lazy import: SeparationEngine (and its heavy deps like torch/torchaudio) are
# only loaded when the user actually clicks "Start Separation", keeping the
# initial window open fast.

# Drag-and-drop is handled via native Windows API (WM_DROPFILES) using
# ctypes with PyGILState_Ensure/Release to avoid GIL crashes on Python 3.12+.

# Ensure the project root is on sys.path so 'code' package is importable
# even when running as `python code/gui_app.py` from the project root.
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_APP_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Load theme before creating window
_theme_path = os.path.join(_PROJECT_ROOT, "theme.json")
if os.path.exists(_theme_path):
    ctk.set_default_color_theme(_theme_path)


class App(WaveformMixin, URLHandlerMixin, HistoryMixin, StemMixerMixin, ctk.CTk):
    """Main application window with file management, controls, and progress tracking."""

    def __init__(self):
        """Main application window for audio/vocal separation."""
        super().__init__()
        self.title("VocalPro")
        self.geometry("960x720")
        self.minsize(720, 540)
        self.resizable(True, True)
        ctk.set_appearance_mode("dark")

        # ── Fast startup: defer heavy work to background threads ──
        # Show the window first, then do icon gen + shortcut creation off-thread.
        self.config = load_config()
        self.engine: Optional["SeparationEngine"] = None  # Cached engine
        self.worker: Optional[SeparationWorker] = None
        self.queue: queue.Queue = queue.Queue()
        self.input_files: list[str] = []  # List of pending files for batch processing
        self._input_files_lock = threading.Lock()  # Guards input_files across threads
        self.current_output_dir: Optional[str] = None
        self._last_url: Optional[str] = None  # Last URL for retry on failure
        self._download_cancel = threading.Event()  # Signal to abort active download
        self._download_in_progress = False  # Guard to prevent concurrent downloads
        self._download_history: list[dict] = self._load_history()  # Persistent download history
        self._separation_history: list[dict] = self._load_sep_history()  # Persistent separation history

        self._ffmpeg_debounce_id: Optional[str] = None  # For debouncing FFmpeg path trace

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.after(500, self._process_queue)
        self.after(200, self._check_dependencies)
        self.after(300, self._deferred_init)

        # Keyboard shortcuts
        self.bind("<Control-o>", lambda e: self.browse_file())
        self.bind("<Control-O>", lambda e: self.browse_file())
        self.bind("<Control-r>", lambda e: self.start_separation())
        self.bind("<Control-R>", lambda e: self.start_separation())
        self.bind("<Escape>", lambda e: self.cancel())

    def _deferred_init(self) -> None:
        """Run icon generation and shortcut creation in a background thread
        so the window appears instantly on first launch."""
        def _bg():
            # Icon generation
            if not os.path.isfile(_APP_ICON):
                try:
                    from code.create_icon import create_icon as _gen_icon
                    _gen_icon(_APP_ICON)
                except Exception:
                    pass
            # Set window icon (must be on main thread for tkinter)
            if os.path.isfile(_APP_ICON):
                try:
                    self.after(0, lambda: self.iconbitmap(_APP_ICON))
                except Exception:
                    pass
            # Desktop shortcut
            create_desktop_shortcut()

        threading.Thread(target=_bg, daemon=True).start()

    # ── Dependency check ────────────────────────────────────────────────

    def _check_dependencies(self) -> None:
        if not check_ffmpeg(self.config.get("ffmpeg_path")):
            self.log("❌  ffmpeg is not installed or path is invalid!")
            self.log("   Download from https://ffmpeg.org/download.html")
            self.log("   Or set custom folder in Advanced Settings.")
            self.status_badge.set_status("ffmpeg missing", _ERROR)
            self.btn_start.configure(state="disabled")
        else:
            self.status_badge.set_status("Ready", _SUCCESS)
            self.btn_start.configure(state="normal")

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.configure(fg_color=_BG)
        self._build_header()

        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=(8, 12))
        content.grid_columnconfigure(0, weight=1)

        self._build_source_dest(content)
        self._build_model_card(content)
        self._build_options_card(content)
        self._build_run_card(content)
        self._build_stem_mixer_card(content)
        self.log("Ready — drop or browse files to begin.")

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(14, 0))
        title_lbl = ctk.CTkLabel(
            header, text="🎵  VocalPro",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=_TEXT,
        )
        title_lbl.pack(anchor="w")
        subtitle = ctk.CTkLabel(
            header, text="Remove background music from any audio or video",
            font=ctk.CTkFont(size=12), text_color=_TEXT_DIM,
        )
        subtitle.pack(anchor="w")

    # ── Card 1: Source + Destination ──────────────────────────────────

    def _build_source_dest(self, content):
        card = Card(content, title="SOURCE & DESTINATION")
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        card.container.grid_columnconfigure(0, weight=1)

        self.drop_zone = DropZone(card.container, on_drop=self._on_file_drop)
        self.drop_zone.pack(fill="x", padx=16, pady=(2, 8))

        browse_frame = ctk.CTkFrame(card.container, fg_color="transparent")
        browse_frame.pack(fill="x", padx=16, pady=(0, 4))

        self.btn_file = GhostButton(
            browse_frame, text="📁  Browse", width=100, command=self.browse_file,
        )
        self.btn_file.pack(side="left")

        self.btn_url = GhostButton(
            browse_frame, text="🔗  URL", width=80, command=self._load_from_url,
        )
        self.btn_url.pack(side="left", padx=(6, 0))

        self.btn_retry = GhostButton(
            browse_frame, text="↻  Retry", width=80, command=self._retry_download,
        )
        self.btn_cancel_dload = DangerButton(
            browse_frame, text="✕  Dload", width=80, command=self._cancel_download,
        )
        self.btn_clear = GhostButton(
            browse_frame, text="🗑️  Clear", width=70, command=self._clear_queue,
        )
        self.btn_clear.pack(side="left", padx=(6, 0))
        self.file_count_badge = ctk.CTkLabel(
            browse_frame, text="",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#FFFFFF", fg_color=_ACCENT,
            corner_radius=8, height=22,
        )

        self.bpm_label = ctk.CTkLabel(
            browse_frame, text="",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_DIM,
        )
        self.bpm_label.pack_forget()

        out_frame = ctk.CTkFrame(card.container, fg_color="transparent")
        out_frame.pack(fill="x", padx=16, pady=(4, 10))

        self.btn_output_dir = GhostButton(
            out_frame, text="📂  Output Folder", width=130,
            command=self.browse_output_dir,
        )
        self.btn_output_dir.pack(side="left")

        default_out = os.path.join(_PROJECT_ROOT, "output_vocals")
        self.current_output_dir = default_out
        self.output_dir_label = ctk.CTkLabel(
            out_frame, text=default_out,
            font=ctk.CTkFont(size=11), text_color=_TEXT_DIM, anchor="w",
        )
        self.output_dir_label.pack(side="left", fill="x", expand=True, padx=(10, 6))

        self.btn_reveal = GhostButton(
            out_frame, text="👁️", width=50,
            command=self._reveal_output_dir,
        )
        self.btn_reveal.pack(side="left")

        # ── Waveform preview ──────────────────────────────────────────
        self._waveform_frame = ctk.CTkFrame(card.container, fg_color="transparent")
        self._waveform_canvas = tk.Canvas(
            self._waveform_frame, height=80, bg=_CARD_TOP, highlightthickness=0,
        )
        self._waveform_canvas.pack(fill="x", padx=16, pady=(0, 2))

        wave_btn_frame = ctk.CTkFrame(self._waveform_frame, fg_color="transparent")
        wave_btn_frame.pack(fill="x", padx=16, pady=(0, 6))

        self._wave_play_btn = GhostButton(
            wave_btn_frame, text="▶ Play", width=60,
            command=self._wave_play_pause,
        )
        self._wave_play_btn.pack(side="left")

        self._wave_stop_btn = DangerButton(
            wave_btn_frame, text="■", width=30, state="disabled",
            command=self._wave_stop,
        )
        self._wave_stop_btn.pack(side="left", padx=(4, 0))

        self._wave_time_label = ctk.CTkLabel(
            wave_btn_frame, text="0:00 / 0:00",
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM,
        )
        self._wave_time_label.pack(side="left", padx=(10, 0))

        self._waveform_frame.pack_forget()  # hidden until file loaded

        # ── Waveform state ────────────────────────────────────────────
        self._wave_audio_data = None
        self._wave_sr = None
        self._wave_is_playing = False
        self._wave_paused = False
        self._wave_pos = 0  # current playback position in samples
        self._wave_cursor_id = None
        self._wave_update_id = None

    # ── Card 2: Model ─────────────────────────────────────────────────

    def _build_model_card(self, content):
        card = Card(content, title="MODEL")
        card.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        row = ctk.CTkFrame(card.container, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            row, text="AI Model:",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=_TEXT,
        ).pack(side="left")

        self.model_var = tk.StringVar(value=self.config.get("model_name", "htdemucs_ft"))
        self._model_descriptions = {
            "htdemucs_ft":   "✅  Best quality — fine-tuned (recommended, ~3.5 GB VRAM)",
            "htdemucs":      "⚡  Faster — base transformer, slightly lower quality",
            "htdemucs_6s":   "🎸  6-stem — isolates piano + guitar as separate tracks",
            "hdemucs_mmi":   "🧠  v3 architecture — different separation profile",
            "mdx":           "🏆  MDX winner — good balance of speed & quality",
            "mdx_extra":     "🔊  MDX extra — more robust with extra training data",
            "mdx_q":         "💾  MDX quantized — smaller, very fast, lower quality",
            "mdx_extra_q":   "💾  MDX extra quantized — good for low VRAM systems",
        }
        model_menu = ctk.CTkOptionMenu(
            row,
            values=list(self._model_descriptions.keys()),
            variable=self.model_var,
            command=lambda _: self._on_model_change(),
            width=140, height=30, corner_radius=6,
            fg_color=_CARD_TOP, button_color=_ACCENT, button_hover_color=_ACCENT_H,
        )
        model_menu.pack(side="left", padx=(8, 14))

        self.btn_advanced = GhostButton(
            row, text="⚙️  Advanced", width=100, height=30,
            command=self._open_advanced_settings,
        )
        self.btn_advanced.pack(side="left")

        self.btn_history = GhostButton(
            row, text="📋  History", width=90, height=30,
            command=self._show_history,
        )
        self.btn_history.pack(side="left", padx=(6, 0))

        self.btn_sep_history = GhostButton(
            row, text="🧬  Sep History", width=100, height=30,
            command=self._show_sep_history,
        )
        self.btn_sep_history.pack(side="left", padx=(6, 0))

        self.model_desc_label = ctk.CTkLabel(
            card.container,
            text=self._model_descriptions.get(self.model_var.get(), ""),
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM, anchor="w",
        )
        self.model_desc_label.pack(fill="x", padx=16, pady=(0, 10))

        # ── Presets row ───────────────────────────────────────────────
        presets_row = ctk.CTkFrame(card.container, fg_color="transparent")
        presets_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            presets_row, text="Preset:",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=_TEXT,
        ).pack(side="left")

        self.preset_var = tk.StringVar()
        self.preset_menu = ctk.CTkOptionMenu(
            presets_row,
            values=[],
            variable=self.preset_var,
            width=140, height=28, corner_radius=6,
            fg_color=_CARD_TOP, button_color=_ACCENT, button_hover_color=_ACCENT_H,
        )
        self.preset_menu.pack(side="left", padx=(8, 6))

        GhostButton(
            presets_row, text="💾 Save", width=60, height=28,
            command=self._save_preset,
        ).pack(side="left", padx=(0, 4))

        GhostButton(
            presets_row, text="📂 Load", width=60, height=28,
            command=self._load_preset,
        ).pack(side="left", padx=(0, 4))

        GhostButton(
            presets_row, text="🗑️", width=40, height=28,
            command=self._delete_preset,
        ).pack(side="left")

        self._refresh_preset_list()

    # ── Card 3: Options ───────────────────────────────────────────────

    def _build_options_card(self, content):
        card = Card(content, title="OPTIONS")
        card.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        self._build_format_selector(card.container)
        self._build_checkboxes(card.container)

    def _build_format_selector(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(10, 4))
        ctk.CTkLabel(
            row, text="Format:",
            font=ctk.CTkFont(size=12, weight="bold"), text_color=_TEXT,
        ).pack(side="left")
        self.format_var = tk.StringVar(value=self.config.get("output_format", "wav"))
        format_menu = ctk.CTkOptionMenu(
            row,
            values=["wav", "mp3", "flac"],
            variable=self.format_var,
            command=lambda _: self._save_ui_settings(),
            width=80, height=28, corner_radius=6,
            fg_color=_CARD_TOP, button_color=_ACCENT, button_hover_color=_ACCENT_H,
        )
        format_menu.pack(side="left", padx=(8, 0))

    def _build_checkboxes(self, parent):
        sections = [
            ("PROCESSING", "Fine-tune how audio is cleaned and separated", [
                ("enable_spectral_denoise", "Reduce background noise (spectral gating)", True),
                ("enable_vocal_gate", "Mute sections without vocals", True),
                ("enable_multiband_denoise", "Multi-band noise reduction (advanced)", True),
                ("enable_noise_profile", "Auto-detect noise from silent segments", True),
                ("adaptive_gate_floor", "Dynamic gate threshold adjustment", True),
                ("trim_silence", "Trim leading/trailing silence", False),
                ("ensemble_mode", "🔀 Ensemble mode (combine model results)", False),
            ]),
            ("OUTPUT", "Choose which files are saved after separation", [
                ("karaoke_mode", "🎤 Karaoke mode (vocals removed)", False),
                ("generate_comparison_samples", "Generate A/B comparison clips", False),
                ("save_background_track", "Save instrumental-only track", False),
                ("include_sfx", "Include SFX in output stems", False),
                ("enable_sfx_separation", "Extract SFX as separate stem (HPSS)", False),
            ]),
        ]
        var_attr = {
            "include_sfx": "include_sfx_var",
            "enable_vocal_gate": "enable_gate_var",
            "enable_spectral_denoise": "enable_denoise_var",
            "generate_comparison_samples": "gen_samples_var",
            "save_background_track": "save_bg_var",
            "trim_silence": "trim_silence_var",
            "enable_multiband_denoise": "enable_multiband_var",
            "enable_noise_profile": "enable_profile_var",
            "adaptive_gate_floor": "adaptive_gate_var",
            "enable_sfx_separation": "sfx_sep_var",
            "karaoke_mode": "karaoke_var",
            "ensemble_mode": "ensemble_var",
        }
        for section_title, section_desc, opts in sections:
            sep = ctk.CTkFrame(parent, fg_color="transparent")
            sep.pack(fill="x", padx=16, pady=(2, 0))
            ctk.CTkLabel(
                sep, text=section_title,
                font=ctk.CTkFont(size=10, weight="bold"), text_color=_TEXT_DIM,
            ).pack(anchor="w")
            ctk.CTkLabel(
                sep, text=section_desc,
                font=ctk.CTkFont(size=9), text_color=_TEXT_DIM,
            ).pack(anchor="w")

            grid = ctk.CTkFrame(parent, fg_color="transparent")
            grid.pack(fill="x", padx=24, pady=(2, 4))
            grid.grid_columnconfigure(0, weight=1)
            grid.grid_columnconfigure(1, weight=1)

            for i, (cfg_key, label, default) in enumerate(opts):
                attr = var_attr[cfg_key]
                var = tk.BooleanVar(value=self.config.get(cfg_key, default))
                setattr(self, attr, var)
                cb = ctk.CTkCheckBox(
                    grid, text=label, variable=var,
                    command=self._save_ui_settings,
                    font=ctk.CTkFont(size=11), text_color=_TEXT_DIM,
                    fg_color=_ACCENT, hover_color=_ACCENT_H, checkmark_color="#FFFFFF",
                )
                cb.grid(row=i // 2, column=i % 2, sticky="w", pady=2)

    # ── Card 4: Run ───────────────────────────────────────────────────

    def _build_run_card(self, content):
        card = Card(content, title="RUN")
        card.grid(row=3, column=0, sticky="ew", pady=(0, 0))

        btn_row = ctk.CTkFrame(card.container, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(10, 6))

        self.btn_start = AccentButton(
            btn_row, text="▶  Start Separation", width=180,
            command=self.start_separation,
        )
        self.btn_start.pack(side="left", padx=(0, 6))

        self.btn_cancel = DangerButton(
            btn_row, text="✕  Cancel", width=100, state="disabled",
            command=self.cancel,
        )
        self.btn_cancel.pack(side="left")
        self.status_badge = StatusBadge(btn_row, text="  Ready  ")
        self.status_badge.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            card.container, height=12, corner_radius=6,
            progress_color=_ACCENT, fg_color=_CARD_TOP,
        )
        self.progress_bar.pack(fill="x", padx=16, pady=(2, 3))
        self.progress_bar.set(0)

        self.overall_progress = ctk.CTkProgressBar(
            card.container, height=5, corner_radius=3,
            progress_color=_SUCCESS, fg_color=_CARD_TOP,
        )
        self.overall_progress.pack(fill="x", padx=16, pady=(0, 8))
        self.overall_progress.set(0)

        log_header = ctk.CTkFrame(card.container, fg_color="transparent")
        log_header.pack(fill="x", padx=14, pady=(0, 0))
        ctk.CTkLabel(
            log_header, text="Log",
            font=ctk.CTkFont(size=10, weight="bold"), text_color=_TEXT_DIM,
        ).pack(side="left")
        GhostButton(
            log_header, text="Clear", width=50, height=20,
            font=ctk.CTkFont(size=9),
            command=self._clear_log,
        ).pack(side="right")

        self.log_text = ctk.CTkTextbox(
            card.container, height=200,
            font=ctk.CTkFont(family="Consolas", size=11) if sys.platform == "win32"
                 else ctk.CTkFont(family="Courier", size=11),
            fg_color=_BG, text_color=_TEXT_DIM,
            border_width=0, corner_radius=8, state="disabled",
        )
        self.log_text.pack(fill="x", padx=14, pady=(4, 10))

    # ── Card 5: Stem Mixer ────────────────────────────────────────────

    def _build_stem_mixer_card(self, content):
        self._stem_mixer_card = Card(content, title="STEM MIXER")
        self._stem_mixer_card.grid(row=4, column=0, sticky="ew", pady=(8, 0))

        self._stem_sliders = {}
        self._stem_mixer_output_dir = None
        self._preview_thread = None
        self._is_playing = False

        # Container for slider rows
        self._stem_slider_frame = ctk.CTkFrame(
            self._stem_mixer_card.container, fg_color="transparent"
        )
        self._stem_slider_frame.pack(fill="x", padx=16, pady=(8, 4))

        # Volume label that shows overall
        self._stem_master_vol = tk.DoubleVar(value=100.0)
        vol_frame = ctk.CTkFrame(self._stem_mixer_card.container, fg_color="transparent")
        vol_frame.pack(fill="x", padx=16, pady=(2, 4))
        ctk.CTkLabel(
            vol_frame, text="Master:",
            font=ctk.CTkFont(size=11, weight="bold"), text_color=_TEXT,
        ).pack(side="left")
        master_slider = ctk.CTkSlider(
            vol_frame, from_=0, to=200, number_of_steps=200,
            variable=self._stem_master_vol,
            command=lambda _: self._update_stem_master_labels(),
            width=200, height=16,
            fg_color=_CARD_TOP, progress_color=_ACCENT, button_color=_ACCENT,
        )
        master_slider.pack(side="left", padx=(8, 4))

        self._stem_master_label = ctk.CTkLabel(
            vol_frame, text="100%",
            font=ctk.CTkFont(size=10), text_color=_TEXT_DIM, width=36,
        )
        self._stem_master_label.pack(side="left")

        # Buttons row
        btn_frame = ctk.CTkFrame(self._stem_mixer_card.container, fg_color="transparent")
        btn_frame.pack(fill="x", padx=16, pady=(4, 8))

        self._btn_preview = GhostButton(
            btn_frame, text="▶ Preview", width=90, command=self._stem_preview,
        )
        self._btn_preview.pack(side="left")

        self._btn_stop = DangerButton(
            btn_frame, text="■ Stop", width=70, state="disabled",
            command=self._stem_stop,
        )
        self._btn_stop.pack(side="left", padx=(6, 0))

        self._btn_export = AccentButton(
            btn_frame, text="💾 Export Mix", width=110, command=self._stem_export,
        )
        self._btn_export.pack(side="left", padx=(6, 0))

        self._btn_midi_all = GhostButton(
            btn_frame, text="🎵 MIDI All", width=90, command=self._stem_midi_all,
        )
        self._btn_midi_all.pack(side="left", padx=(6, 0))

        self._btn_export_sep = GhostButton(
            btn_frame, text="📦 Export All (Custom)", width=150,
            command=self._stem_export_separate,
        )
        self._btn_export_sep.pack(side="left", padx=(6, 0))

        self._btn_reset = GhostButton(
            btn_frame, text="↺ Reset", width=70, command=self._stem_reset,
        )
        self._btn_reset.pack(side="left", padx=(6, 0))

        # Hide the card initially (shown after separation completes)
        self._stem_mixer_card.grid_remove()

    # ── URL loading ────────────────────────────────────────────────────

    @staticmethod
    def _format_size(num_bytes: float) -> str:
        """Human-readable byte size (O(1) via integer log2)."""
        from math import log2
        if num_bytes <= 0:
            return f"{num_bytes:.1f} B"
        units = ("B", "KB", "MB", "GB", "TB")
        idx = min(int(log2(num_bytes) // 10), len(units) - 1)
        return f"{num_bytes / (1024 ** idx):.1f} {units[idx]}"

    def _on_file_drop(self, data: str) -> None:
        """Handle files/URLs dropped onto the drop zone."""
        # Native drop handler sends multiple paths: "path1\r\n{path2 with spaces}\r\npath3"
        raw = data.strip()
        # Split on \r\n or \n, strip braces from individual paths
        paths = []
        for p in re.split(r"[\r\n]+", raw):
            p = p.strip("{} \t")
            if p:
                paths.append(p)
        
        valid_files = []
        for path in paths:
            path = path.strip()
            if not path:
                continue
            # Handle URLs
            if path.startswith(("http://", "https://")):
                self._download_url(path)
                continue
            
            ext = os.path.splitext(path)[1].lower()
            if ext not in _SUPPORTED_EXTS:
                self.log(f"⚠️  Skipping unsupported file: {os.path.basename(path)}")
                continue
            if not os.path.isfile(path):
                self.log(f"⚠️  File not found: {path}")
                continue
            valid_files.append(path)
        
        if valid_files:
            with self._input_files_lock:
                self.input_files.extend(valid_files)
                self.input_files = list(dict.fromkeys(self.input_files))
            self._update_file_label()
            self.log(f"Added {len(valid_files)} files to queue.")

    # ── File browsing ───────────────────────────────────────────────────

    def browse_file(self) -> None:
        """Open a file dialog to select audio/video files for processing."""
        fpaths = filedialog.askopenfilenames(
            title="Select files",
            filetypes=[
                ("All supported", "*.mp4 *.mkv *.avi *.mov *.flv *.mp3 *.wav *.flac *.ogg"),
                ("Video", "*.mp4 *.mkv *.avi *.mov *.flv"),
                ("Audio", "*.mp3 *.wav *.flac *.ogg"),
            ],
        )
        if fpaths:
            with self._input_files_lock:
                self.input_files.extend(list(fpaths))
                self.input_files = list(dict.fromkeys(self.input_files))
            self._update_file_label()
            self.log(f"Added {len(fpaths)} files to queue.")

    def _detect_bpm(self, path: str) -> str:
        """Detect tempo (BPM) of an audio file using librosa."""
        try:
            y, sr = librosa.load(path, duration=30, res_type="kaiser_fast")
            if len(y) < sr:  # less than 1 second
                return ""
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            bpm = float(tempo.item() if hasattr(tempo, 'item') else tempo)
            if bpm > 0:
                return f" {round(bpm)} BPM"
        except Exception:
            pass
        return ""

    @staticmethod
    def _detect_key(path: str) -> str:
        """Detect musical key of an audio file using chroma features."""
        try:
            y, sr = librosa.load(path, duration=30, res_type="kaiser_fast")
            if len(y) < sr:
                return ""
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            chroma_mean = chroma.mean(axis=1)

            # Krumhansl-Schmuckler key profiles
            major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
            key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

            best_corr = -1.0
            best_key = ""
            for i in range(12):
                corr_major = np.corrcoef(np.roll(major_profile, i), chroma_mean)[0, 1]
                corr_minor = np.corrcoef(np.roll(minor_profile, i), chroma_mean)[0, 1]
                if corr_major > best_corr:
                    best_corr = corr_major
                    best_key = f"{key_names[i]} major"
                if corr_minor > best_corr:
                    best_corr = corr_minor
                    best_key = f"{key_names[i]} minor"
            return best_key if best_corr > 0.1 else ""
        except Exception:
            return ""

    def _update_file_label(self) -> None:
        count = len(self.input_files)
        if count == 0:
            self.drop_zone.reset()
            self.file_count_badge.pack_forget()
            self.bpm_label.pack_forget()
            self._waveform_frame.pack_forget()
            self._wave_stop()
        elif count == 1:
            name = os.path.basename(self.input_files[0])
            self.drop_zone.set_file(name)
            self.file_count_badge.pack_forget()
            self.bpm_label.configure(text="")
            self.bpm_label.pack(side="left", padx=(8, 0))
            self.after(100, lambda p=self.input_files[0]: self._show_bpm(p))
            self.after(200, lambda p=self.input_files[0]: self._load_waveform(p))
        else:
            first_name = os.path.basename(self.input_files[0])
            self.drop_zone.set_file(f"{first_name} + {count - 1} more")
            # Pop-in animation: amber flash then settle to green
            self.file_count_badge.configure(text=str(count), fg_color=_WARNING)
            if not self.file_count_badge.winfo_manager():
                self.file_count_badge.pack(side="left", padx=(2, 0))
            self.after(150, lambda b=self.file_count_badge: b.configure(fg_color=_SUCCESS))
            self.bpm_label.pack_forget()
            self._waveform_frame.pack_forget()

    def _show_bpm(self, path: str) -> None:
        # Re-check it's still the only file in the queue
        if len(self.input_files) != 1 or self.input_files[0] != path:
            self.bpm_label.pack_forget()
            return
        bpm = self._detect_bpm(path)
        key = self._detect_key(path) if bpm else ""
        parts = [p for p in [bpm, key] if p]
        text = "  ".join(parts) if parts else ""
        if text and len(self.input_files) == 1 and self.input_files[0] == path:
            self.bpm_label.configure(text=text)
            self.bpm_label.pack(side="left", padx=(8, 0))
        else:
            self.bpm_label.pack_forget()

    # ── Waveform preview helpers ────────────────────────────────────────

    def _clear_queue(self) -> None:
        """Empty the file queue."""
        with self._input_files_lock:
            self.input_files = []
        self._update_file_label()
        self.btn_retry.pack_forget()
        self.log("Queue cleared.")

    # ── Output folder browsing ──────────────────────────────────────────

    def browse_output_dir(self) -> None:
        """Open a folder picker dialog for the output directory."""
        initial = self.current_output_dir or _APP_DIR
        folder = filedialog.askdirectory(
            title="Choose output folder",
            initialdir=initial,
        )
        if folder:
            self.current_output_dir = folder
            self.output_dir_label.configure(text=folder, text_color=_TEXT)
            self.log(f"Output folder: {folder}")

    def _reveal_output_dir(self) -> None:
        """Open the current output directory in the system file explorer."""
        folder = self.current_output_dir or os.path.join(_PROJECT_ROOT, "output_vocals")
        if not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder], check=False)
            else:
                subprocess.run(["xdg-open", folder], check=False)
        except Exception as e:
            self.log(f"⚠️  Could not open folder: {e}")

    # ── Separation control ──────────────────────────────────────────────

    def start_separation(self) -> None:
        """Begin processing all queued files through the separation engine."""
        if self.worker and self.worker.is_alive():
            self.log("⏳ Already processing — please wait for the current batch to finish.")
            return
        if not self.input_files:
            self.log("Please select or drop files first.")
            return

        # Filter out missing files
        valid_files = [f for f in self.input_files if os.path.isfile(f)]
        if not valid_files:
            self.log("❌  Selected files no longer exist on disk.")
            with self._input_files_lock:
                self.input_files = []
            self._update_file_label()
            return
        
        with self._input_files_lock:
            self.input_files = valid_files
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0)
        self.status_badge.set_status("Processing batch…", _WARNING)

        # Ensure output directory exists
        output_dir = self.current_output_dir or os.path.join(_PROJECT_ROOT, "output_vocals")
        os.makedirs(output_dir, exist_ok=True)
        self.current_output_dir = output_dir

        self.worker = SeparationWorker(
            self,  # Pass the app instance
            list(self.input_files), output_dir,
            self.queue,
            include_sfx=bool(self.include_sfx_var.get()),
            enable_gate=bool(self.enable_gate_var.get()),
            enable_denoise=bool(self.enable_denoise_var.get()),
            gen_samples=bool(self.gen_samples_var.get()),
            save_bg=bool(self.save_bg_var.get()),
            trim_silence=bool(self.trim_silence_var.get()),
            enable_multiband=bool(self.enable_multiband_var.get()),
            enable_profile=bool(self.enable_profile_var.get()),
            adaptive_gate=bool(self.adaptive_gate_var.get()),
            sfx_separation=bool(self.sfx_sep_var.get()),
            karaoke_mode=bool(self.karaoke_var.get()),
            output_format=self.format_var.get(),
        )
        self.worker.start()

    def cancel(self) -> None:
        """Request cancellation of the currently running separation process."""
        if self.worker and self.worker.is_alive():
            self.worker.stop()
            self.log("Cancelling…")
            self.status_badge.set_status("Cancelling…", _WARNING)

    # ── Queue processing ────────────────────────────────────────────────

    def _process_queue(self) -> None:
        try:
            while True:
                msg = self.queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    pct, text = msg[1], msg[2]
                    # pct here is overall_pct from worker
                    total = len(self.input_files)
                    curr_file_idx = getattr(self.worker, "current_file_idx", 0)
                    
                    # Estimate current file progress vs overall
                    # The worker sends (self.current_file_idx / total * 100) + (percent / total)
                    # We can set the main bar to the percent part.
                    self.overall_progress.set(pct / 100)
                    
                    # Extract the individual file percentage from the overall percentage
                    if total > 0:
                        file_pct = (pct - (curr_file_idx / total * 100)) * total
                        self.progress_bar.set(min(max(file_pct / 100, 0.0), 1.0))

                    self.status_badge.set_status(text, _TEXT_DIM)
                    self.log(text)

                elif kind == "download":
                    pct, text = msg[1], msg[2]
                    dl_path = msg[3] if len(msg) > 3 else None
                    if pct >= 100:
                        # Download complete — update the drop zone and reset status
                        if dl_path:
                            with self._input_files_lock:
                                self.input_files.append(dl_path)
                        self.progress_bar.set(1.0)
                        self._update_file_label()
                        self._last_url = None  # Clear retry state on success
                        self.btn_retry.pack_forget()
                        self.btn_cancel_dload.pack_forget()
                        if not (self.worker and self.worker.is_alive()):
                            self.status_badge.set_status("Ready", _SUCCESS)
                        self.log(text)
                    elif pct >= 0:
                        self.progress_bar.set(min(max(pct / 100.0, 0.0), 1.0))
                        self.status_badge.set_status(f"Downloading {pct:.0f}%", _WARNING)
                        self.log(text)
                    else:
                        self.status_badge.set_status("Downloading…", _WARNING)
                        self.log(text)

                elif kind == "done":
                    output_path = msg[1]
                    # Record separation history before clearing files
                    sep_files = list(self.input_files)
                    self._add_sep_history(
                        sep_files, self.model_var.get(),
                        self.current_output_dir or "",
                        "success",
                         settings={k: self.config.get(k) for k in _SETTINGS_KEYS},
                    )
                    self.progress_bar.set(1.0)
                    self.status_badge.set_status("Batch Complete ✓", _SUCCESS)
                    self.log("✅  All files processed successfully.")
                    
                    processed = self.worker.input_files if self.worker else []
                    with self._input_files_lock:
                        self.input_files = [f for f in self.input_files if f not in processed]
                    self._update_file_label()
                    self._reset_buttons()
                    
                    if output_path:
                        folder = os.path.dirname(os.path.abspath(output_path))
                        try:
                            if sys.platform == "win32":
                                os.startfile(folder)
                            else:
                                subprocess.run(["xdg-open", folder], check=False)
                        except Exception:
                            pass
                        # Populate stem mixer with available stems
                        self.after(500, lambda d=folder: self._populate_stem_mixer(d))

                elif kind == "error":
                    self.status_badge.set_status("Error", _ERROR)
                    self.log(f"Error: {msg[1]}")
                    # Record separation history on error (not a download error)
                    if not self._last_url and self.input_files:
                        self._add_sep_history(
                            self.input_files, self.model_var.get(),
                            self.current_output_dir or "",
                            "error",
                            settings={k: self.config.get(k) for k in _SETTINGS_KEYS},
                        )
                    self._reset_buttons()
                    self.btn_cancel_dload.pack_forget()
                    # Show retry button if this was a download error
                    if self._last_url and not self.btn_retry.winfo_manager():
                        self.btn_retry.pack(side="left", padx=(6, 0))

                elif kind == "cancelled":
                    self.status_badge.set_status("Cancelled", _WARNING)
                    # Record separation history on cancel
                    self._add_sep_history(
                        self.input_files, self.model_var.get(),
                        self.current_output_dir or "",
                        "cancelled",
                        settings={k: self.config.get(k) for k in _SETTINGS_KEYS},
                    )
                    self.btn_cancel_dload.pack_forget()
                    self._reset_buttons()

        except queue.Empty:
            pass
        except Exception:
            import traceback
            traceback.print_exc()
        self.after(500, self._process_queue)

    def _reset_buttons(self) -> None:
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.progress_bar.set(0)
        self.overall_progress.set(0)

    def _on_model_change(self) -> None:
        """Update model description label and save settings when model selection changes."""
        model = self.model_var.get()
        self.model_desc_label.configure(
            text=self._model_descriptions.get(model, "")
        )
        self._save_ui_settings()

    def _save_ui_settings(self) -> None:
        """Update the internal config dict and save to disk."""
        self.config["include_sfx"] = bool(self.include_sfx_var.get())
        self.config["enable_vocal_gate"] = bool(self.enable_gate_var.get())
        self.config["enable_spectral_denoise"] = bool(self.enable_denoise_var.get())
        self.config["generate_comparison_samples"] = bool(self.gen_samples_var.get())
        self.config["save_background_track"] = bool(self.save_bg_var.get())
        self.config["trim_silence"] = bool(self.trim_silence_var.get())
        self.config["enable_multiband_denoise"] = bool(self.enable_multiband_var.get())
        self.config["enable_noise_profile"] = bool(self.enable_profile_var.get())
        self.config["adaptive_gate_floor"] = bool(self.adaptive_gate_var.get())
        self.config["enable_sfx_separation"] = bool(self.sfx_sep_var.get())
        self.config["karaoke_mode"] = bool(self.karaoke_var.get())
        self.config["ensemble_mode"] = bool(self.ensemble_var.get())
        self.config["output_format"] = self.format_var.get()
        self.config["model_name"] = self.model_var.get()
        save_config(self.config)

    # ── Presets ──────────────────────────────────────────────────────────

    def _refresh_preset_list(self) -> None:
        """Scan presets dir and populate the preset dropdown."""
        presets = []
        if os.path.isdir(_PRESETS_DIR):
            for f in sorted(os.listdir(_PRESETS_DIR)):
                if f.endswith(".json"):
                    presets.append(f[:-5])
        old_val = self.preset_var.get()
        self.preset_menu.configure(values=presets if presets else [""])
        if presets:
            if old_val in presets:
                self.preset_var.set(old_val)
            else:
                self.preset_var.set(presets[0] if old_val not in presets else old_val)
        else:
            self.preset_var.set("")

    def _save_preset(self) -> None:
        """Prompt for a name and save current config as a preset."""
        # Use a simple dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Save Preset")
        dialog.geometry("320x160")
        dialog.configure(fg_color=_BG)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Preset name:",
            font=ctk.CTkFont(size=12), text_color=_TEXT,
        ).pack(padx=20, pady=(20, 8), anchor="w")

        entry = ctk.CTkEntry(
            dialog, placeholder_text="My preset",
            fg_color=_CARD_TOP, border_color=_BORDER, text_color=_TEXT,
        )
        entry.pack(padx=20, fill="x", pady=(0, 12))

        def _do_save():
            name = entry.get().strip()
            if not name:
                return
            path = os.path.join(_PRESETS_DIR, f"{name}.json")
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                                  delete=False, dir=_PRESETS_DIR) as tf:
                    json.dump(self.config, tf, indent=2)
                    tmp = tf.name
                os.replace(tmp, path)
                self._refresh_preset_list()
                self.preset_var.set(name)
                self.log(f"Preset saved: {name}")
            except Exception as e:
                self.log(f"Failed to save preset: {e}")
            dialog.destroy()

        ctk.CTkButton(
            dialog, text="Save", command=_do_save,
            fg_color=_ACCENT, hover_color=_ACCENT_H, text_color="#FFFFFF",
            width=80, height=30, corner_radius=6,
        ).pack(pady=(0, 12))

    def _load_preset(self) -> None:
        """Load the selected preset into the UI."""
        name = self.preset_var.get().strip()
        if not name:
            self.log("No preset selected.")
            return
        path = os.path.join(_PRESETS_DIR, f"{name}.json")
        if not os.path.isfile(path):
            self.log(f"Preset file not found: {path}")
            return
        try:
            with open(path, "r") as f:
                preset = json.load(f)
        except Exception as e:
            self.log(f"Failed to load preset: {e}")
            return
        self.config.update(preset)
        # Apply to UI variables
        self.model_var.set(self.config.get("model_name", "htdemucs_ft"))
        self._on_model_change()
        self.format_var.set(self.config.get("output_format", "wav"))
        for cfg_key, attr_name in [
            ("include_sfx", "include_sfx_var"),
            ("enable_vocal_gate", "enable_gate_var"),
            ("enable_spectral_denoise", "enable_denoise_var"),
            ("generate_comparison_samples", "gen_samples_var"),
            ("save_background_track", "save_bg_var"),
            ("trim_silence", "trim_silence_var"),
            ("enable_multiband_denoise", "enable_multiband_var"),
            ("enable_noise_profile", "enable_profile_var"),
            ("adaptive_gate_floor", "adaptive_gate_var"),
            ("enable_sfx_separation", "sfx_sep_var"),
            ("karaoke_mode", "karaoke_var"),
            ("ensemble_mode", "ensemble_var"),
        ]:
            try:
                getattr(self, attr_name).set(self.config.get(cfg_key, False))
            except Exception:
                pass
        save_config(self.config)
        self.log(f"Preset loaded: {name}")

    def _delete_preset(self) -> None:
        """Delete the selected preset file."""
        name = self.preset_var.get().strip()
        if not name:
            self.log("No preset selected.")
            return
        path = os.path.join(_PRESETS_DIR, f"{name}.json")
        if not os.path.isfile(path):
            self.log(f"Preset not found: {name}")
            return
        try:
            os.remove(path)
            self._refresh_preset_list()
            self.log(f"Preset deleted: {name}")
        except Exception as e:
            self.log(f"Failed to delete preset: {e}")

    # ── Stem Mixer ────────────────────────────────────────────────────────

    def _open_advanced_settings(self) -> None:
        """Open a dialog to tune internal parameters."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Advanced Settings")
        dialog.geometry("500x480")
        dialog.configure(fg_color=_BG)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="⚙️ Advanced Tuning",
            font=ctk.CTkFont(size=18, weight="bold"), text_color=_TEXT,
        ).pack(pady=(20, 16))

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=320)
        scroll.pack(fill="both", expand=True, padx=20)

        # Helper to create a slider with label and a reset-to-default button
        def create_setting(master, label, key, min_val, max_val, is_int=False, default_val=None):
            if default_val is None:
                default_val = DEFAULT_CONFIG.get(key, min_val)

            frame = ctk.CTkFrame(master, fg_color="transparent")
            frame.pack(fill="x", pady=8)
            
            lbl_frame = ctk.CTkFrame(frame, fg_color="transparent")
            lbl_frame.pack(fill="x")
            
            ctk.CTkLabel(lbl_frame, text=label, font=ctk.CTkFont(size=13), text_color=_TEXT).pack(side="left")

            # Value label + reset button side-by-side
            val_reset_frame = ctk.CTkFrame(lbl_frame, fg_color="transparent")
            val_reset_frame.pack(side="right")

            val_lbl = ctk.CTkLabel(val_reset_frame, text="", font=ctk.CTkFont(size=12), text_color=_ACCENT)
            val_lbl.pack(side="left")

            reset_btn = ctk.CTkButton(
                val_reset_frame,
                text="↺",
                width=26, height=20,
                font=ctk.CTkFont(size=11),
                fg_color="transparent",
                hover_color=_CARD_TOP,
                text_color=_TEXT_DIM,
                corner_radius=4,
            )
            reset_btn.pack(side="left", padx=(4, 0))

            curr_val = self.config.get(key, default_val)
            
            _save_timer = [None]
            def on_change(v):
                v = float(v)
                if is_int:
                    v = int(round(v))
                self.config[key] = v
                val_lbl.configure(text=str(v))
                if _save_timer[0]:
                    self.after_cancel(_save_timer[0])
                _save_timer[0] = self.after(300, lambda: save_config(self.config))

            def on_reset():
                d = default_val
                slider.set(d)
                on_change(d)

            reset_btn.configure(command=on_reset)

            slider = ctk.CTkSlider(
                frame, from_=min_val, to=max_val,
                command=on_change,
                button_color=_ACCENT, button_hover_color=_ACCENT_H, progress_color=_ACCENT,
            )
            slider.set(curr_val)
            slider.pack(fill="x", pady=(4, 0))
            val_lbl.configure(text=str(curr_val))

        create_setting(scroll, "Segment Length (sec) [Higher = Better Quality, more VRAM]", "segment", 2.0, 30.0)
        create_setting(scroll, "Overlap (sec)", "overlap", 0.1, 8.0)
        create_setting(scroll, "Model Passes (Shifts) [1=Fast, 3+=Slow/Better]", "shifts", 1, 10, is_int=True)
        create_setting(scroll, "Vocal Gate Threshold (dB) [Lower = More sensitive]", "gate_threshold_db", -80.0, -10.0)
        create_setting(scroll, "Gate Floor (dB) [Lower = quieter silence]", "gate_floor_db", -90.0, -20.0)
        create_setting(scroll, "Denoise Strength (0.0 - 1.0)", "denoise_strength", 0.0, 1.0)
        create_setting(scroll, "Multi-band: Low Band Strength (rumble)", "denoise_strength_low", 0.0, 1.0)
        create_setting(scroll, "Multi-band: Mid Band Strength (vocals)", "denoise_strength_mid", 0.0, 1.0)
        create_setting(scroll, "Multi-band: High Band Strength (hiss)", "denoise_strength_high", 0.0, 1.0)
        create_setting(scroll, "Large File Threshold (min)", "large_file_threshold_minutes", 1, 120, is_int=True)

        # FFmpeg Path
        ff_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        ff_frame.pack(fill="x", pady=12)
        ctk.CTkLabel(ff_frame, text="FFmpeg Binaries Folder (optional):", font=ctk.CTkFont(size=13), text_color=_TEXT).pack(side="top", anchor="w")
        
        ff_entry_frame = ctk.CTkFrame(ff_frame, fg_color="transparent")
        ff_entry_frame.pack(fill="x", pady=(4, 0))
        
        ff_var = tk.StringVar(value=self.config.get("ffmpeg_path", ""))
        ff_entry = ctk.CTkEntry(ff_entry_frame, textvariable=ff_var, height=32, fg_color=_CARD_TOP, border_color=_BORDER)
        ff_entry.pack(side="left", fill="x", expand=True)
        
        def browse_ff():
            folder = filedialog.askdirectory(title="Select FFmpeg bin folder")
            if folder:
                ff_var.set(folder)
                self.config["ffmpeg_path"] = folder
                save_config(self.config)
                self._check_dependencies()

        GhostButton(ff_entry_frame, text="📁", width=40, height=32, command=browse_ff).pack(side="right", padx=(8, 0))

        # Re-check on type (debounced to avoid subprocess on every keystroke)
        def _debounce_ffmpeg(*_):
            if self._ffmpeg_debounce_id:
                self.after_cancel(self._ffmpeg_debounce_id)
            self._ffmpeg_debounce_id = self.after(500, lambda: (
                self.config.update({"ffmpeg_path": ff_var.get()}),
                save_config(self.config),
                self._check_dependencies()
            ))
        ff_var.trace_add("write", _debounce_ffmpeg)

        AccentButton(dialog, text="Close & Save", width=120, command=dialog.destroy).pack(pady=20)

    def _on_closing(self) -> None:
        """Handle window close event with confirmation if busy."""
        if self.worker and self.worker.is_alive():
            from tkinter import messagebox
            if messagebox.askokcancel("Quit", "VocalPro is currently processing files. Are you sure you want to cancel and quit?"):
                self.worker.stop()
                self.worker.join(timeout=10)
        try:
            self.destroy()
        finally:
            # Exit gracefully — atexit handlers (e.g., temp file cleanup) will run.
            sys.exit(0)

    # ── Logging ─────────────────────────────────────────────────────────

    def log(self, message: str) -> None:
        """Append a message to the log output text widget."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        """Clear all text from the log output widget."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")


# ── Background worker ───────────────────────────────────────────────────

class SeparationWorker(threading.Thread):
    """Background thread that runs audio separation batches with progress reporting."""

    def __init__(
        self,
        app: "App",
        input_files: list[str],
        output_dir: str,
        progress_queue: queue.Queue,
        include_sfx: bool = False,
        enable_gate: bool = True,
        enable_denoise: bool = True,
        gen_samples: bool = False,
        save_bg: bool = False,
        trim_silence: bool = False,
        enable_multiband: bool = True,
        enable_profile: bool = True,
        adaptive_gate: bool = True,
        sfx_separation: bool = False,
        karaoke_mode: bool = False,
        output_format: str = "wav",
    ) -> None:
        """Background thread that runs audio separation with progress reporting."""
        super().__init__(daemon=True)
        self.app = app
        self.config = app.config
        self.input_files = input_files
        self.output_dir = output_dir
        self.progress_queue = progress_queue
        self.cancel_event = threading.Event()
        self.include_sfx = include_sfx
        self.enable_gate = enable_gate
        self.enable_denoise = enable_denoise
        self.gen_samples = gen_samples
        self.save_bg = save_bg
        self.trim_silence = trim_silence
        self.enable_multiband = enable_multiband
        self.enable_profile = enable_profile
        self.adaptive_gate = adaptive_gate
        self.sfx_separation = sfx_separation
        self.karaoke_mode = karaoke_mode
        self.output_format = output_format
        self.current_file_idx = 0

    def stop(self) -> None:
        """Signal the worker thread to cancel processing at the next opportunity."""
        self.cancel_event.set()

    def run(self) -> None:
        """Execute the separation batch: initialize engine, process each file, clean up."""
        try:
            import torch
            from code.separation_engine import SeparationEngine

            engine_config = {
                **self.config,
                "include_sfx": self.include_sfx,
                "enable_vocal_gate": self.enable_gate,
                "enable_spectral_denoise": self.enable_denoise,
                "generate_comparison_samples": self.gen_samples,
                "save_background_track": self.save_bg,
                "trim_silence": self.trim_silence,
                "enable_multiband_denoise": self.enable_multiband,
                "enable_noise_profile": self.enable_profile,
                "adaptive_gate_floor": self.adaptive_gate,
                "enable_sfx_separation": self.sfx_separation,
                "karaoke_mode": self.karaoke_mode,
                "output_format": self.output_format,
            }

            _notify = lambda: self.app.after(0, self.app._process_queue)  # wake queue processor

            # Use persistent engine from app or create it
            if self.app.engine is None:
                self.progress_queue.put((
                    "progress", 1,
                    "Initializing AI engine (first run downloads models)..."
                ))
                _notify()
                self.app.engine = SeparationEngine(
                    engine_config,
                    progress_callback=self._report_progress,
                    cancel_event=self.cancel_event,
                )
            else:
                # Update engine state for this run
                self.app.engine.update_config(engine_config)
                self.app.engine.progress_callback = self._report_progress
                self.app.engine.cancel_event = self.cancel_event
                self.cancel_event.clear()

            total = len(self.input_files)
            last_output = None
            
            for i, file_path in enumerate(self.input_files):
                if self.cancel_event.is_set():
                    break
                
                self.current_file_idx = i
                self.current_file_name = os.path.basename(file_path)
                
                self.progress_queue.put((
                    "progress", (i / total * 100), 
                    f"[{i+1}/{total}] Starting: {self.current_file_name}"
                ))
                _notify()
                
                last_output = self.app.engine.separate_file(file_path, self.output_dir)
                
                # Cleanup between files
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

            if self.cancel_event.is_set():
                self.progress_queue.put(("cancelled", None))
            else:
                self.progress_queue.put(("done", last_output))
            _notify()

        except InterruptedError:
            self.progress_queue.put(("cancelled", None))
            _notify()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.progress_queue.put(("error", str(e)))
            _notify()

    def _report_progress(self, percent: float, msg: str) -> None:
        total = len(self.input_files)
        # Adjust percent to reflect overall batch progress
        overall_pct = (self.current_file_idx / total * 100) + (percent / total)
        display_msg = f"[{self.current_file_idx + 1}/{total}] {msg}"
        self.progress_queue.put(("progress", overall_pct, display_msg))


# ── Entry point ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
