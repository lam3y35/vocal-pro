"""Application configuration management.

Loads defaults and merges with any user overrides stored in ~/.vocalpro_config.json.
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    # Model settings
    "model_name": "htdemucs",           # best CPU/GPU balance — fast, good quality
    "segment": 6.0,                     # CPU-friendly; increase for better quality
    "overlap": 2.0,                     # more overlap = smoother crossfade
    "shifts": 1,                        # 1=fast, 5+=slow/best quality

    # Output
    "output_format": "wav",             # "wav" | "mp3" | "flac"
    "output_all_stems": False,
    "device": "auto",                   # "auto" | "cuda" | "cpu"

    # Large file chunking
    "large_file_threshold_minutes": 15,
    "chunk_duration_minutes": 12,
    "overlap_seconds": 5,

    # Video output
    "output_video": True,
    "audio_bitrate": "320k",
    "ffmpeg_faststart": True,
    "ffmpeg_path": "",                 # Optional: custom path to ffmpeg folder
    "progress_update_interval_seconds": 0.5,

    # SFX: extract sound effects from background music and mix into the main output.
    # SFX is never saved as a standalone file — it's mixed directly into the vocals
    # file (normal mode) or the karaoke instrumental (song mode).
    "include_sfx": True,
    "save_background_track": False,
    "generate_comparison_samples": False,
    "trim_silence": True,               # Trim leading/trailing silence from vocals

    # Post-processing: vocal quality enhancement
    # Balanced for CPU: single-band is much faster than multiband (3x fewer
    # noisereduce calls) and denoise_strength=0.55 is audibly effective.
    "enable_vocal_gate": True,        # silence instrumental-only sections
    "enable_spectral_denoise": True,  # reduce residual music bleed
    "gate_threshold_db": -55.0,       # more sensitive vocal detection (dB)
    "gate_floor_db": -60.0,           # quieter silenced sections (dB)
    "denoise_strength": 0.55,         # balanced — audibly effective without artifacts (0-1)
    "min_vocal_duration": 0.08,       # minimum vocal segment to keep (seconds)
    "enable_multiband_denoise": False,# single-band is faster & with higher strength gives same quality
    "denoise_band_split_hz": [250.0, 6000.0],  # [low_cut, high_cut] for multi-band split
    "denoise_strength_low": 0.35,     # gentle rumble reduction
    "denoise_strength_mid": 0.10,     # minimal denoising in vocal range — preserves detail
    "denoise_strength_high": 0.25,    # light denoising on highs — keeps sibilants and air
    "enable_noise_profile": False,    # noise profile extraction adds time; single-band estimates noise from signal
    "adaptive_gate_floor": False,     # simpler fixed floor works well with stronger denoising

    # SFX separation from background music
    # Extracts percussive sound effects (SFX) from the background music "other" stem.
    # The SFX is mixed into the main output (vocals or karaoke instrumental) — never
    # saved as a standalone file.
    # Disabled by default on CPU — HPSS adds ~2-3s processing time for marginal benefit.
    "enable_sfx_separation": False,
    "sfx_separation_margin_db": 5.0, # HPSS symmetric margin (higher = more aggressive separation)
    "sfx_kernel_size": 15,            # HPSS kernel size (smaller = better transient capture)
    "sfx_margin_harmonic_db": 3.0,    # HPSS harmonic margin (higher = pushes more content to SFX)
    "sfx_margin_percussive_db": 1.0,  # HPSS percussive margin (lower = keeps more content as SFX)

    # Special modes
    "karaoke_mode": False,           # Export instrumental (all non-vocal stems summed)
    "ensemble_mode": False,          # Merge results from multiple models for best quality

    # Performance
    "safe_mode": False,
    "max_threads": 0,                  # 0 = auto-detect (use all available cores)
    "cooldown_between_chunks_seconds": 0.0,

    # UI behavior
    # If True, automatically load waveform and show play controls when a single
    # file is added to the queue. Set to False to disable auto-preview.
    "auto_preview": False,

    # Output selection for video inputs: 'both' keeps both muxed video and audio file,
    # 'video_only' keeps only muxed video (audio file deleted after mux),
    # 'audio_only' keeps only audio files and does not mux back to video.
    "video_output_mode": "both",
}

# Validation constraints: (min_value, max_value)
_VALIDATION: dict[str, tuple[float, float]] = {
    "segment": (0.5, 60.0),
    "overlap": (0.0, 30.0),
    "shifts": (0, 20),
    "large_file_threshold_minutes": (1, 480),
    "chunk_duration_minutes": (1, 120),
    "overlap_seconds": (0, 60),
    "max_threads": (0, 128),
    "cooldown_between_chunks_seconds": (0.0, 60.0),
    "progress_update_interval_seconds": (0.1, 10.0),
    "gate_threshold_db": (-80.0, 0.0),
    "gate_floor_db": (-120.0, -20.0),
    "denoise_strength": (0.0, 1.0),
    "min_vocal_duration": (0.01, 5.0),
    "denoise_strength_low": (0.0, 1.0),
    "denoise_strength_mid": (0.0, 1.0),
    "denoise_strength_high": (0.0, 1.0),
    "sfx_separation_margin_db": (1.0, 30.0),
    "sfx_kernel_size": (5, 99),
    "sfx_margin_harmonic_db": (0.0, 30.0),
    "sfx_margin_percussive_db": (0.0, 30.0),
}

_OLD_CONFIG_FILE = Path.home() / ".vocal_remover_pro_config.json"
CONFIG_FILE = Path.home() / ".vocalpro_config.json"

# Migrate from old config file name on first access
if _OLD_CONFIG_FILE.exists() and not CONFIG_FILE.exists():
    try:
        shutil.move(str(_OLD_CONFIG_FILE), str(CONFIG_FILE))
        logger.info("Migrated config from %s to %s", _OLD_CONFIG_FILE, CONFIG_FILE)
    except OSError as e:
        logger.warning("Failed to migrate old config: %s", e)


def _validate(cfg: dict[str, Any]) -> dict[str, Any]:
    """Clamp config values to safe ranges. Returns the validated config."""
    for key, (lo, hi) in _VALIDATION.items():
        if key in cfg:
            # Complex types (lists, dicts) are invalid for numeric config keys — reset to default
            if isinstance(cfg[key], (list, dict)):
                cfg[key] = DEFAULT_CONFIG[key]
                continue
            # Bools are valid (True/False → 1.0/0.0), just clamp
            if isinstance(cfg[key], bool):
                continue
            try:
                val = float(cfg[key])
                if val < lo or val > hi:
                    logger.warning("Config '%s' value %s out of range [%s, %s], clamping", key, val, lo, hi)
                    cfg[key] = type(cfg[key])(max(lo, min(hi, val)))
            except (TypeError, ValueError):
                logger.warning("Config '%s' has invalid type, resetting to default", key)
                cfg[key] = DEFAULT_CONFIG[key]
    return cfg


def _get_device_overrides() -> dict[str, Any]:
    """Return device-appropriate overrides for keys still at factory default.

    DEFAULT_CONFIG now has CPU-friendly defaults (htdemucs, shifts=1, segment=6).
    On GPU systems this overrides to high-quality defaults suitable for CUDA.
    """
    try:
        import torch
        if torch.cuda.is_available():
            return {
                "model_name": "htdemucs_ft",     # best quality for GPU
                "shifts": 5,                      # shift averaging ≈ better quality
                "segment": 24.0,                  # larger segments = better quality
            }
    except Exception:
        pass
    # CPU users already have optimal defaults in DEFAULT_CONFIG
    return {}


def load_config() -> dict[str, Any]:
    """Load config from disk, merge with defaults, validate, apply device
    optimizations, and return."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg.update(user_cfg)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read config file %s: %s", CONFIG_FILE, e)
    cfg = _validate(cfg)

    # Apply device-optimized defaults for keys the user hasn't explicitly
    # overridden (i.e. they're still at DEFAULT_CONFIG value). This ensures
    # CPU users get fast defaults out of the box without clobbering manual
    # tuning.
    overrides = _get_device_overrides()
    for key, val in overrides.items():
        if key in cfg and cfg[key] == DEFAULT_CONFIG[key]:
            cfg[key] = val

    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    """Save config to disk atomically (excluding defaults that haven't changed)."""
    import tempfile
    to_save = {k: v for k, v in cfg.items() if k in DEFAULT_CONFIG}
    try:
        fd, tmp = tempfile.mkstemp(suffix=".json", dir=str(CONFIG_FILE.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(to_save, f, indent=4)
        os.replace(tmp, CONFIG_FILE)
    except OSError as e:
        logger.error("Failed to save config file %s: %s", CONFIG_FILE, e)
