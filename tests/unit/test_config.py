"""Tests for code.config — defaults, validation, clamping, save/load."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ════════════════════════════════════════════════════════════════════════
# Config tests
# ════════════════════════════════════════════════════════════════════════

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

    def test_save_skips_unknown(self):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("{}"); f.close()
        try:
            with patch("code.config.CONFIG_FILE", Path(f.name)):
                from code.config import save_config
                save_config({"unknown": 42})
                with open(f.name, encoding="utf-8") as fh:
                    assert "unknown" not in json.load(fh)
        finally:
            os.unlink(f.name)

    def test_validate_preserves_bool(self):
        from code.config import _validate
        assert _validate({"enable_vocal_gate": True})["enable_vocal_gate"] is True

    def test_validate_preserves_str(self):
        from code.config import _validate
        assert _validate({"model_name": "mdx_extra"})["model_name"] == "mdx_extra"

    def test_validation_ranges_valid(self, cfg):
        from code.config import _VALIDATION
        for k, (lo, hi) in _VALIDATION.items():
            v = float(cfg[k])
            assert lo <= v <= hi

    def test_default_not_mutated(self):
        from code.config import DEFAULT_CONFIG, _validate
        orig = DEFAULT_CONFIG.copy()
        _validate({"segment": 999})
        assert DEFAULT_CONFIG == orig

    @pytest.mark.parametrize("key,val,exp", [
        ("segment", 0.4, 0.5), ("segment", 70, 60.0),
        ("overlap", -0.1, 0.0), ("overlap", 35, 30.0),
        ("shifts", -1, 0), ("shifts", 25, 20),
        ("large_file_threshold_minutes", 0, 1),
        ("large_file_threshold_minutes", 500, 480),
        ("chunk_duration_minutes", 0, 1),
        ("chunk_duration_minutes", 200, 120),
        ("overlap_seconds", -1, 0), ("overlap_seconds", 70, 60),
        ("max_threads", -1, 0), ("max_threads", 200, 128),
        ("cooldown_between_chunks_seconds", -1, 0.0),
        ("cooldown_between_chunks_seconds", 70, 60.0),
        ("progress_update_interval_seconds", 0.05, 0.1),
        ("gate_threshold_db", -90, -80.0), ("gate_threshold_db", 10, 0.0),
        ("gate_floor_db", -130, -120.0), ("gate_floor_db", -10, -20.0),
        ("denoise_strength", -0.1, 0.0), ("denoise_strength", 1.5, 1.0),
        ("min_vocal_duration", 0.005, 0.01), ("min_vocal_duration", 6, 5.0),
    ])
    def test_clamp_param(self, key, val, exp):
        from code.config import _validate
        r = _validate({key: val})
        assert r[key] == exp or abs(r[key] - exp) < 1e-6


# ════════════════════════════════════════════════════════════════════════
# Bulk / parametrized config tests
# ════════════════════════════════════════════════════════════════════════

class TestBulkConfig:
    @pytest.mark.parametrize("key,val", [
        ("segment", 0.5), ("segment", 1.0), ("segment", 8.0), ("segment", 16.0),
        ("denoise_strength_low", 0.0), ("denoise_strength_low", 0.5), ("denoise_strength_low", 1.0),
        ("denoise_strength_mid", 0.0), ("denoise_strength_mid", 0.5), ("denoise_strength_mid", 1.0),
        ("denoise_strength_high", 0.0), ("denoise_strength_high", 0.5), ("denoise_strength_high", 1.0),
        ("segment", 30.0), ("segment", 60.0),
        ("overlap", 0.0), ("overlap", 0.25), ("overlap", 0.5), ("overlap", 1.0),
        ("overlap", 2.0), ("overlap", 5.0), ("overlap", 10.0), ("overlap", 30.0),
        ("shifts", 0), ("shifts", 1), ("shifts", 2), ("shifts", 3), ("shifts", 5),
        ("shifts", 10), ("shifts", 20),
        ("gate_threshold_db", -80), ("gate_threshold_db", -60), ("gate_threshold_db", -40),
        ("gate_threshold_db", -20), ("gate_threshold_db", 0),
        ("gate_floor_db", -120), ("gate_floor_db", -80), ("gate_floor_db", -60),
        ("gate_floor_db", -40), ("gate_floor_db", -20),
        ("denoise_strength", 0.0), ("denoise_strength", 0.25), ("denoise_strength", 0.5),
        ("denoise_strength", 0.75), ("denoise_strength", 1.0),
        ("min_vocal_duration", 0.01), ("min_vocal_duration", 0.1), ("min_vocal_duration", 0.5),
        ("min_vocal_duration", 1.0), ("min_vocal_duration", 5.0),
        ("max_threads", 0), ("max_threads", 1), ("max_threads", 2), ("max_threads", 4),
        ("max_threads", 8), ("max_threads", 16), ("max_threads", 128),
        ("cooldown_between_chunks_seconds", 0.0), ("cooldown_between_chunks_seconds", 0.5),
        ("cooldown_between_chunks_seconds", 1.0), ("cooldown_between_chunks_seconds", 5.0),
        ("cooldown_between_chunks_seconds", 60.0),
        ("large_file_threshold_minutes", 1), ("large_file_threshold_minutes", 5),
        ("large_file_threshold_minutes", 15), ("large_file_threshold_minutes", 30),
        ("large_file_threshold_minutes", 60), ("large_file_threshold_minutes", 480),
        ("chunk_duration_minutes", 1), ("chunk_duration_minutes", 5), ("chunk_duration_minutes", 10),
        ("chunk_duration_minutes", 30), ("chunk_duration_minutes", 120),
        ("overlap_seconds", 0), ("overlap_seconds", 1), ("overlap_seconds", 5),
        ("overlap_seconds", 10), ("overlap_seconds", 30), ("overlap_seconds", 60),
        ("progress_update_interval_seconds", 0.1), ("progress_update_interval_seconds", 0.5),
        ("progress_update_interval_seconds", 1.0), ("progress_update_interval_seconds", 5.0),
    ])
    def test_validate_valid_ranges(self, key, val):
        from code.config import _validate
        r = _validate({key: val})
        assert r[key] == val or abs(r[key] - val) < 1e-6

    @pytest.mark.parametrize("cfg_in", [
        {"model_name": "mdx_extra"}, {"model_name": "htdemucs"},
        {"model_name": "hdemucs_mmi"}, {"model_name": "mdx_q"},
        {"output_format": "wav"}, {"output_format": "mp3"}, {"output_format": "flac"},
        {"device": "cpu"}, {"device": "auto"},
        {"enable_vocal_gate": True}, {"enable_vocal_gate": False},
        {"enable_spectral_denoise": True}, {"enable_spectral_denoise": False},
        {"include_sfx": True}, {"include_sfx": False},
        {"save_background_track": True}, {"save_background_track": False},
        {"generate_comparison_samples": True}, {"generate_comparison_samples": False},
        {"trim_silence": True}, {"trim_silence": False},
        {"output_video": True}, {"output_video": False},
        {"ffmpeg_faststart": True}, {"ffmpeg_faststart": False},
        {"safe_mode": True}, {"safe_mode": False},
        {"output_all_stems": True}, {"output_all_stems": False},
        {"audio_bitrate": "128k"}, {"audio_bitrate": "192k"},
        {"audio_bitrate": "320k"}, {"audio_bitrate": "lossless"},
        {"ffmpeg_path": ""}, {"ffmpeg_path": "C:/ffmpeg/bin"},
    ])
    def test_validate_preserves_values(self, cfg_in):
        from code.config import _validate
        r = _validate(dict(cfg_in))
        for k, v in cfg_in.items():
            assert r[k] == v

    @pytest.mark.parametrize("bad,key,lo,hi", [
        ("not_a_number", "segment", 0.5, 60.0),
        ([], "segment", 0.5, 60.0),
        ({}, "segment", 0.5, 60.0),
        ("bad", "overlap", 0.0, 30.0),
        ("bad", "shifts", 0, 20),
        ("bad", "max_threads", 0, 128),
        ("bad", "denoise_strength", 0.0, 1.0),
    ])
    def test_validate_non_numeric_defaults(self, bad, key, lo, hi):
        from code.config import _validate
        r = _validate({key: bad})
        assert lo <= r[key] <= hi

    @pytest.mark.parametrize("key", [
        "model_name", "output_format", "device", "ffmpeg_path", "audio_bitrate",
    ])
    def test_validate_str_keys_preserved(self, key):
        from code.config import _validate
        r = _validate({key: "test_value"})
        assert r[key] == "test_value"

    @pytest.mark.parametrize("key", [
        "include_sfx", "enable_vocal_gate", "enable_spectral_denoise",
        "generate_comparison_samples", "save_background_track", "trim_silence",
        "output_video", "ffmpeg_faststart", "safe_mode", "output_all_stems",
        "enable_multiband_denoise", "enable_noise_profile", "adaptive_gate_floor",
        "enable_sfx_separation",
    ])
    def test_validate_bool_keys(self, key):
        from code.config import _validate
        assert _validate({key: True})[key] is True
        assert _validate({key: False})[key] is False
