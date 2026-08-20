import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConfig:
    def test_default_has_all_keys(self, cfg):
        for k in ["model_name", "segment", "overlap", "shifts", "output_format",
                   "device", "enable_vocal_gate", "enable_spectral_denoise",
                   "gate_threshold_db", "gate_floor_db", "denoise_strength",
                   "min_vocal_duration", "safe_mode", "max_threads",
                   "cooldown_between_chunks_seconds", "large_file_threshold_minutes",
                   "chunk_duration_minutes", "overlap_seconds", "output_video",
                   "audio_bitrate", "ffmpeg_faststart", "ffmpeg_path",
                   "include_sfx", "save_background_track", "generate_comparison_samples",
                   "trim_silence", "output_all_stems", "progress_update_interval_seconds",
                   "enable_multiband_denoise", "denoise_band_split_hz",
                   "denoise_strength_low", "denoise_strength_mid", "denoise_strength_high",
                   "enable_noise_profile", "adaptive_gate_floor",
                   "enable_sfx_separation", "sfx_separation_margin_db"]:
            assert k in cfg

    def test_no_duplicate_keys(self, cfg):
        assert len(cfg) == len(set(cfg))

    def test_output_format(self, cfg):
        assert cfg["output_format"] in ("wav", "mp3", "flac")

    def test_load_no_file(self):
        with patch("code.config.CONFIG_FILE", Path("/nonexistent/.x.json")):
            from code.config import load_config
            assert load_config()["model_name"] == "htdemucs_ft"

    def test_load_corrupt_json(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("{{{bad"); f.close()
        try:
            with patch("code.config.CONFIG_FILE", Path(f.name)):
                from code.config import DEFAULT_CONFIG, load_config
                cfg = load_config()
                assert cfg["segment"] == DEFAULT_CONFIG["segment"]
        finally:
            os.unlink(f.name)

    def test_load_empty(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write(""); f.close()
        try:
            with patch("code.config.CONFIG_FILE", Path(f.name)):
                from code.config import DEFAULT_CONFIG, load_config
                cfg = load_config()
                assert cfg["segment"] == DEFAULT_CONFIG["segment"]
        finally:
            os.unlink(f.name)

    def test_load_merges(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({"segment": 8.0, "shifts": 2}, f); f.close()
        try:
            with patch("code.config.CONFIG_FILE", Path(f.name)):
                from code.config import load_config
                c = load_config()
                assert c["segment"] == 8.0 and c["shifts"] == 2 and c["model_name"] == "htdemucs_ft"
        finally:
            os.unlink(f.name)

    def test_clamp_segment_high(self):
        from code.config import _validate
        assert _validate({"segment": 999})["segment"] <= 60.0

    def test_clamp_segment_low(self):
        from code.config import _validate
        assert _validate({"segment": 0.1})["segment"] >= 0.5

    def test_clamp_shifts_high(self):
        from code.config import _validate
        assert _validate({"shifts": 100})["shifts"] <= 20

    def test_clamp_shifts_low(self):
        from code.config import _validate
        assert _validate({"shifts": -5})["shifts"] >= 0

    def test_clamp_overlap_high(self):
        from code.config import _validate
        assert _validate({"overlap": 50})["overlap"] <= 30.0

    def test_clamp_overlap_low(self):
        from code.config import _validate
        assert _validate({"overlap": -1})["overlap"] >= 0.0

    def test_clamp_large_file(self):
        from code.config import _validate
        assert _validate({"large_file_threshold_minutes": 999})["large_file_threshold_minutes"] <= 480

    def test_clamp_chunk(self):
        from code.config import _validate
        assert _validate({"chunk_duration_minutes": 999})["chunk_duration_minutes"] <= 120

    def test_clamp_overlap_sec(self):
        from code.config import _validate
        assert _validate({"overlap_seconds": 999})["overlap_seconds"] <= 60

    def test_clamp_threads(self):
        from code.config import _validate
        assert _validate({"max_threads": 999})["max_threads"] <= 128

    def test_clamp_cooldown(self):
        from code.config import _validate
        assert _validate({"cooldown_between_chunks_seconds": 999})["cooldown_between_chunks_seconds"] <= 60.0

    def test_clamp_progress(self):
        from code.config import _validate
        assert _validate({"progress_update_interval_seconds": 0.01})["progress_update_interval_seconds"] >= 0.1

    def test_clamp_gate_thresh_upper(self):
        from code.config import _validate
        assert _validate({"gate_threshold_db": 10})["gate_threshold_db"] <= 0.0

    def test_clamp_gate_thresh_lower(self):
        from code.config import _validate
        assert _validate({"gate_threshold_db": -100})["gate_threshold_db"] >= -80.0

    def test_clamp_gate_floor(self):
        from code.config import _validate
        assert _validate({"gate_floor_db": 10})["gate_floor_db"] <= -20.0

    def test_clamp_denoise_high(self):
        from code.config import _validate
        assert _validate({"denoise_strength": 5})["denoise_strength"] <= 1.0

    def test_clamp_denoise_low(self):
        from code.config import _validate
        assert _validate({"denoise_strength": -1})["denoise_strength"] >= 0.0

    def test_clamp_min_vocal(self):
        from code.config import _validate
        assert _validate({"min_vocal_duration": 10})["min_vocal_duration"] <= 5.0

    def test_validate_non_numeric(self):
        from code.config import _validate
        assert isinstance(_validate({"segment": "bad"})["segment"], float)

    def test_validate_none(self):
        from code.config import _validate
        assert isinstance(_validate({"segment": None})["segment"], float)

    def test_save(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump({}, f); f.close()
        try:
            with patch("code.config.CONFIG_FILE", Path(f.name)):
                from code.config import save_config
                save_config({"model_name": "mdx"})
                with open(f.name, encoding="utf-8") as fh:
                    assert json.load(fh)["model_name"] == "mdx"
        finally:
            os.unlink(f.name)
