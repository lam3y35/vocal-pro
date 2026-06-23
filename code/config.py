"""Application configuration management.

Loads defaults and merges with any user overrides stored in ~/.vocal_remover_pro_config.json.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    # Model settings
    "model_name": "htdemucs_ft",       # fine-tuned model, best quality, ~3.5GB VRAM
    "segment": 24.0,                    # larger = better quality, more VRAM
    "overlap": 2.0,                     # more overlap = smoother crossfade
    "shifts": 5,                        # more passes = best quality (1=fast)

    # Output
    "output_format": "wav",             # "wav" | "mp3" | "flac"
    "output_all_stems": True,
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

    # SFX: mix vocals with htdemucs "other" stem (sound effects, foley, ambience)
    "include_sfx": True,
    "save_background_track": True,      # Save the full-length music track
    "generate_comparison_samples": True, # Extract 3 random clips for comparison
    "trim_silence": True,               # Trim leading/trailing silence from vocals

    # Post-processing: vocal quality enhancement
    "enable_vocal_gate": True,        # silence instrumental-only sections
    "enable_spectral_denoise": True,  # reduce residual music bleed
    "gate_threshold_db": -45.0,       # more sensitive vocal detection (dB)
    "gate_floor_db": -60.0,           # quieter silenced sections (dB)
    "denoise_strength": 0.90,         # aggressive noise removal (0-1)
    "min_vocal_duration": 0.1,        # minimum vocal segment to keep (seconds)
    "enable_multiband_denoise": True, # split signal into bands and denoise each separately
    "denoise_band_split_hz": [250.0, 6000.0],  # [low_cut, high_cut] for multi-band split
    "denoise_strength_low": 0.90,     # denoise strength for low band (rumble)
    "denoise_strength_mid": 0.75,     # denoise strength for mid band (vocal range)
    "denoise_strength_high": 0.85,    # denoise strength for high band (hiss)
    "enable_noise_profile": True,     # extract noise profile from VAD-silent sections
    "adaptive_gate_floor": True,      # compute gate floor from actual noise floor

    # SFX separation from background music
    "enable_sfx_separation": True,    # split "other" stem into music + SFX via HPSS
    "sfx_separation_margin_db": 5.0, # HPSS margin (higher = more aggressive separation)

    # Special modes
    "karaoke_mode": False,           # Export instrumental (all non-vocal stems summed)
    "ensemble_mode": False,          # Merge results from multiple models for best quality

    # Performance
    "safe_mode": False,
    "max_threads": 0,                  # 0 = auto-detect (use all available cores)
    "cooldown_between_chunks_seconds": 0.0,
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
}

CONFIG_FILE = Path.home() / ".vocal_remover_pro_config.json"


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


def load_config() -> dict[str, Any]:
    """Load config from disk, merge with defaults, validate, and return."""
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            cfg.update(user_cfg)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to read config file %s: %s", CONFIG_FILE, e)
    return _validate(cfg)


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
