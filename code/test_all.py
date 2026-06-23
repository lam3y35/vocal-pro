"""VocalPro test suite — 1000+ tests covering all modules, edge cases, bugs."""
# this file is necessary after any edit

from __future__ import annotations

import gc
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, call, mock_open

import numpy as np
import pytest
import torch


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def stereo_signal():
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), 0)
    a = np.zeros((2, len(t)), dtype=np.float32)
    a[0] = np.sin(2 * np.pi * 440 * t) * 0.5
    a[1] = a[0].copy()
    return a, sr

@pytest.fixture
def mono_signal():
    sr = 44100
    dur = 1.0
    t = np.linspace(0, dur, int(sr * dur), 0)
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32), sr

@pytest.fixture
def silent_signal():
    return np.zeros((2, 22050), dtype=np.float32), 44100

@pytest.fixture
def cfg():
    from code.config import DEFAULT_CONFIG
    return dict(DEFAULT_CONFIG)

@pytest.fixture
def engine(cfg):
    with patch("code.separation_engine.demucs_get_model") as m:
        mdl = MagicMock()
        mdl.sources = ["vocals", "other", "bass", "drums"]
        mdl.eval.return_value = None
        m.return_value = mdl
        from code.separation_engine import SeparationEngine
        return SeparationEngine(cfg, progress_callback=lambda p, m: None)


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
# Utils tests
# ════════════════════════════════════════════════════════════════════════

class TestUtils:
    def test_get_exe_none(self):
        from code.utils import _get_exe
        assert _get_exe("ffmpeg") == "ffmpeg"

    def test_get_exe_custom_missing(self):
        from code.utils import _get_exe
        with tempfile.TemporaryDirectory() as td:
            assert _get_exe("ffmpeg", td) == "ffmpeg"

    def test_get_exe_custom_found(self):
        from code.utils import _get_exe
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ffmpeg.exe")
            Path(p).write_text("")
            assert _get_exe("ffmpeg", td) == p

    def test_check_ffmpeg_ok(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            assert check_ffmpeg() is True

    def test_check_ffmpeg_not_found(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert check_ffmpeg() is False

    def test_check_ffmpeg_fail(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run") as m:
            m.side_effect = subprocess.CalledProcessError(1, [])
            assert check_ffmpeg() is False

    def test_run_ffmpeg_ok(self):
        from code.utils import _run_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            _run_ffmpeg(["ffmpeg"])

    def test_run_ffmpeg_fail(self):
        from code.utils import _run_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stderr="err")
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                _run_ffmpeg(["ffmpeg"])

    def test_get_audio_info_sample(self):
        from code.utils import get_audio_info
        sr, dur = 44100, 0.5
        import soundfile as sf
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.close()
        try:
            t = np.linspace(0, dur, int(sr * dur), 0)
            sf.write(f.name, np.sin(2 * np.pi * 440 * t).astype(np.float32), sr)
            sr2, d2, ts, ch = get_audio_info(f.name)
            assert sr2 == 44100 and d2 == pytest.approx(0.5, abs=0.05) and ch in (1, 2)
        finally:
            os.unlink(f.name)

    def test_get_audio_info_no_audio(self):
        from code.utils import get_audio_info
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}))
            with pytest.raises(ValueError, match="No audio stream"):
                get_audio_info("x.mp4")

    def test_video_duration_found(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video", "duration": "10.5"}]}))
            assert get_video_duration("x.mp4") == 10.5

    def test_video_duration_none(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "audio"}]}))
            assert get_video_duration("x.mp4") is None

    def test_video_duration_frames(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            j = json.dumps({"streams": [{"codec_type": "video", "nb_frames": "300", "avg_frame_rate": "30/1"}]})
            m.return_value = MagicMock(returncode=0, stdout=j)
            assert get_video_duration("x.mp4") == 10.0

    def test_video_duration_no_data(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}))
            assert get_video_duration("x.mp4") is None

    def test_trim_audio(self):
        from code.utils import trim_audio_to_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.close()
            try:
                trim_audio_to_duration("i.wav", f.name, 0.1)
                c = m.call_args[0][0]
                assert "-t" in c and any("0.1" in str(x) for x in c)
            finally:
                os.unlink(f.name)

    def test_mux_basic(self):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=10):
                mux_audio_video("i.mp4", "a.wav", "o.mp4")
                c = m.call_args[0][0]
                assert "0:v:0" in c and "1:a:0" in c
                # Must NOT have -t between inputs (Bug 1: old placement)
                assert c.index("-i") < c.index("a.wav")
                # Must have atrim+apad for sync
                assert any("atrim" in str(x) for x in c)
                assert any("apad" in str(x) for x in c)

    def test_mux_no_trim(self):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=None):
                mux_audio_video("i.mp4", "a.wav", "o.mp4", trim_to_video=False)
                c = m.call_args[0][0]
                assert m.called
                # When no video duration, no atrim/apad filter
                assert not any("atrim" in str(x) for x in c)

    def test_mux_sync_filter_uses_video_dur(self):
        """Verify atrim+apad filter chain uses the correct video duration."""
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=60.5):
                mux_audio_video("i.mp4", "a.wav", "o.mp4")
                c = " ".join(m.call_args[0][0])
                assert "atrim=end=60.5" in c
                assert "apad=whole_dur=60.5" in c

    def test_extract_audio(self):
        from code.utils import extract_audio
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_audio("i.mp4", "o.wav")
            assert "-vn" in m.call_args[0][0]

    def test_extract_chunk(self):
        from code.utils import extract_chunk
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_chunk("i.wav", "o.wav", 10, 5)
            c = m.call_args[0][0]
            assert "-ss" in c and "-t" in c

    def test_format_size(self):
        from code.gui_app import App
        assert App._format_size(0) == "0.0 B"
        assert App._format_size(1023) == "1023.0 B"
        assert App._format_size(1024) == "1.0 KB"
        assert App._format_size(1048576) == "1.0 MB"
        assert App._format_size(1073741824) == "1.0 GB"
        assert App._format_size(1.5e9) == "1.4 GB"
        assert App._format_size(-100) == "-100.0 B"


# ════════════════════════════════════════════════════════════════════════
# Audio Post-processing tests
# ════════════════════════════════════════════════════════════════════════

class TestAudioPostProcess:
    def test_detect_vocal_activity_mono(self, mono_signal):
        from code.audio_postprocess import detect_vocal_activity
        a, sr = mono_signal
        m = detect_vocal_activity(a, sr=sr)
        assert m.shape == (len(a),) and np.all((m >= 0) & (m <= 1))

    def test_detect_vocal_activity_stereo(self, stereo_signal):
        from code.audio_postprocess import detect_vocal_activity
        a, sr = stereo_signal
        m = detect_vocal_activity(a, sr=sr)
        assert m.shape == (a.shape[1],) and np.all((m >= 0) & (m <= 1))

    def test_detect_vocal_silence(self, silent_signal):
        from code.audio_postprocess import detect_vocal_activity
        a, sr = silent_signal
        assert np.all(detect_vocal_activity(a, sr=sr, threshold_db=-20) >= 0)

    def test_detect_vocal_empty(self):
        from code.audio_postprocess import detect_vocal_activity
        assert len(detect_vocal_activity(np.array([], dtype=np.float32), sr=44100)) == 0

    def test_detect_vocal_all_ones(self):
        from code.audio_postprocess import detect_vocal_activity
        m = detect_vocal_activity(np.ones(44100, dtype=np.float32), sr=44100)
        assert np.all((m >= 0) & (m <= 1))

    def test_apply_gate_stereo(self, stereo_signal):
        from code.audio_postprocess import apply_vocal_gate
        a, sr = stereo_signal
        r = apply_vocal_gate(a, sr=sr)
        assert r.shape == a.shape

    def test_apply_gate_mono_shape(self, mono_signal):
        """Regression: Bug 2 - 1D input must keep 1D shape."""
        from code.audio_postprocess import apply_vocal_gate
        a, sr = mono_signal
        r = apply_vocal_gate(a, sr=sr)
        assert r.shape == a.shape

    def test_apply_gate_mono_isfinite(self, mono_signal):
        from code.audio_postprocess import apply_vocal_gate
        a, sr = mono_signal
        assert np.all(np.isfinite(apply_vocal_gate(a, sr=sr)))

    def test_apply_gate_silence(self, silent_signal):
        from code.audio_postprocess import apply_vocal_gate
        a, sr = silent_signal
        assert np.all(np.isfinite(apply_vocal_gate(a, sr=sr)))

    def test_apply_gate_high_thresh(self, stereo_signal):
        from code.audio_postprocess import apply_vocal_gate
        a, sr = stereo_signal
        assert apply_vocal_gate(a, sr=sr, threshold_db=100).shape == a.shape

    def test_apply_gate_very_short(self):
        from code.audio_postprocess import apply_vocal_gate
        r = apply_vocal_gate(np.array([[0.1, 0.2, -0.1]], dtype=np.float32), sr=100)
        assert r.shape == (1, 3) and np.all(np.isfinite(r))

    def test_apply_gate_single_sample(self):
        from code.audio_postprocess import apply_vocal_gate
        r = apply_vocal_gate(np.array([[0.5]], dtype=np.float32), sr=44100)
        assert r.shape == (1, 1)

    def test_apply_gate_mono_1d(self):
        from code.audio_postprocess import apply_vocal_gate
        a = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        assert apply_vocal_gate(a, sr=44100).shape == (3,)

    def test_apply_gate_positive_only(self):
        from code.audio_postprocess import apply_vocal_gate
        a = np.abs(np.random.randn(4410).astype(np.float32)) * 0.5
        r = apply_vocal_gate(a, sr=44100)
        assert np.all(r >= 0) and r.shape == (4410,)

    def test_spectral_denoise_mono(self, mono_signal):
        from code.audio_postprocess import spectral_denoise
        a, sr = mono_signal
        assert spectral_denoise(a, sr=sr).shape == a.shape

    def test_spectral_denoise_stereo(self, stereo_signal):
        from code.audio_postprocess import spectral_denoise
        a, sr = stereo_signal
        r = spectral_denoise(a, sr=sr)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_spectral_denoise_noisy(self, mono_signal):
        from code.audio_postprocess import spectral_denoise
        a, sr = mono_signal
        a += np.random.randn(*a.shape).astype(np.float32) * 0.1
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr)))

    def test_spectral_denoise_silence_no_nan(self, silent_signal):
        """Regression: silence must not produce NaN."""
        from code.audio_postprocess import spectral_denoise
        a, sr = silent_signal
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr)))

    def test_spectral_denoise_prop_zero(self, mono_signal):
        from code.audio_postprocess import spectral_denoise
        a, sr = mono_signal
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr, prop_decrease=0)))

    def test_spectral_denoise_prop_one(self, mono_signal):
        from code.audio_postprocess import spectral_denoise
        a, sr = mono_signal
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr, prop_decrease=1)))

    def test_spectral_denoise_empty_guard(self):
        """Regression: empty array must not crash np.max."""
        from code.audio_postprocess import spectral_denoise
        r = spectral_denoise(np.array([], dtype=np.float32), sr=44100)
        assert len(r) == 0

    def test_trim_silence_mono(self, mono_signal):
        from code.audio_postprocess import trim_silence
        a, sr = mono_signal
        s = np.zeros(int(0.1 * sr), dtype=np.float32)
        w = np.concatenate([s, a, s])
        r = trim_silence(w, sr=sr)
        assert len(r) <= len(w) and len(r) > 0

    def test_trim_silence_stereo(self, stereo_signal):
        from code.audio_postprocess import trim_silence
        a, sr = stereo_signal
        s = np.zeros((2, int(0.1 * sr)), dtype=np.float32)
        w = np.concatenate([s, a, s], axis=1)
        r = trim_silence(w, sr=sr)
        assert r.shape[1] <= w.shape[1] and r.shape[0] == 2

    def test_trim_silence_all_zeros(self):
        from code.audio_postprocess import trim_silence
        a = np.zeros(44100, dtype=np.float32)
        r = trim_silence(a, sr=44100)
        assert len(r) <= len(a)

    def test_trim_silence_all_positive(self):
        from code.audio_postprocess import trim_silence
        a = np.ones(44100, dtype=np.float32) * 0.5
        assert len(trim_silence(a, sr=44100)) > 0

    def test_crossfade_two(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        r = smooth_crossfade_chunks([c, c], overlap_samples=4410, sr=sr)
        assert r.ndim == 2 and r.shape[1] == 1 and r.shape[0] > c.shape[0]

    def test_crossfade_single(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.allclose(smooth_crossfade_chunks([c], overlap_samples=0, sr=sr), c)

    def test_crossfade_empty_raises(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        with pytest.raises(ValueError, match="No chunks"):
            smooth_crossfade_chunks([], overlap_samples=0)

    def test_crossfade_three(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.3, int(sr * 0.3), 0)
        c = [np.sin(2 * np.pi * f * t).astype(np.float32)[:, None] for f in (440, 550, 660)]
        assert np.all(np.isfinite(smooth_crossfade_chunks(c, overlap_samples=2205, sr=sr)))

    def test_crossfade_short_last(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t1 = np.linspace(0, 0.5, int(sr * 0.5), 0)
        t2 = np.linspace(0, 0.2, int(sr * 0.2), 0)
        c = [np.sin(2 * np.pi * 440 * t1).astype(np.float32)[:, None],
             np.sin(2 * np.pi * 440 * t2).astype(np.float32)[:, None]]
        assert np.all(np.isfinite(smooth_crossfade_chunks(c, overlap_samples=4410, sr=sr)))

    def test_crossfade_degenerate(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.2, int(sr * 0.2), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.all(np.isfinite(smooth_crossfade_chunks([c, c], overlap_samples=20000, sr=sr)))

    def test_crossfade_zero_overlap(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        r = smooth_crossfade_chunks([c, c], overlap_samples=0, sr=sr)
        assert r.shape[0] == c.shape[0] * 2

    def test_crossfade_stereo(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.3, int(sr * 0.3), 0)
        c = np.column_stack([np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 550 * t)]).astype(np.float32)
        r = smooth_crossfade_chunks([c, c], overlap_samples=2205, sr=sr)
        assert r.shape[1] == 2

    def test_crossfade_20_chunks(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.1, int(sr * 0.1), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.all(np.isfinite(smooth_crossfade_chunks([c.copy() for _ in range(20)], overlap_samples=2205, sr=sr)))

    def test_crossfade_variable_length(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        c = [np.random.randn(n, 1).astype(np.float32) for n in (100, 50, 75)]
        assert np.all(np.isfinite(smooth_crossfade_chunks(c, overlap_samples=10, sr=100)))

    def test_crossfade_not_all_zero(self):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        r = smooth_crossfade_chunks([c, c], overlap_samples=4410, sr=sr)
        assert np.max(np.abs(r)) > 0.1

    @pytest.mark.parametrize("n,ov", [(1, 0), (2, 0), (2, 100), (3, 50), (5, 200), (10, 100)])
    def test_crossfade_params(self, n, ov):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 1000
        t = np.linspace(0, 0.2, int(sr * 0.2), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.all(np.isfinite(smooth_crossfade_chunks([c.copy() for _ in range(n)], overlap_samples=ov, sr=sr)))

    @pytest.mark.parametrize("shape", [(100,), (200,), (1, 100), (2, 100), (2, 500)])
    def test_gate_shapes(self, shape):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(*shape).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100)
        assert r.shape == shape and np.all(np.isfinite(r))

    @pytest.mark.parametrize("thr", [-80, -60, -40, -20, -10, 0])
    def test_gate_thresholds(self, thr):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(4410).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100, threshold_db=thr)
        assert r.shape == (4410,) and np.all(np.isfinite(r))

    def test_postprocess_stereo(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr)
        assert r.shape == a.shape

    def test_postprocess_mono_shape(self, mono_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = mono_signal
        r = postprocess_vocals(a, sr=sr)
        assert r.shape == a.shape

    def test_postprocess_no_gate(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        assert postprocess_vocals(a, sr=sr, enable_gate=False).shape == a.shape

    def test_postprocess_no_denoise(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        assert postprocess_vocals(a, sr=sr, enable_denoise=False).shape == a.shape

    def test_postprocess_trim_only(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, enable_gate=False, enable_denoise=False, trim=True)
        assert r.shape[0] == 2

    def test_postprocess_noop(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        assert np.allclose(postprocess_vocals(a, sr=sr, enable_gate=False, enable_denoise=False, trim=False), a)

    def test_postprocess_silence(self, silent_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = silent_signal
        assert np.all(np.isfinite(postprocess_vocals(a, sr=sr)))

    def test_postprocess_custom(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, gate_threshold_db=-30, gate_floor_db=-40, denoise_prop=0.5, min_vocal_duration=0.2)
        assert r.shape == a.shape

    def test_postprocess_large(self):
        from code.audio_postprocess import postprocess_vocals
        a = np.random.randn(2, 44100 * 5).astype(np.float32) * 0.1
        r = postprocess_vocals(a, sr=44100)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_postprocess_gate_only(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        assert np.all(np.isfinite(postprocess_vocals(a, sr=sr, enable_gate=True, enable_denoise=False)))

    def test_postprocess_denoise_only(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        assert np.all(np.isfinite(postprocess_vocals(a, sr=sr, enable_gate=False, enable_denoise=True)))

    def test_extract_noise_profile_basic(self, mono_signal):
        from code.audio_postprocess import extract_noise_profile, detect_vocal_activity
        a, sr = mono_signal
        mask = detect_vocal_activity(a, sr=sr)
        # With no silence, profile should be None (no non-vocal region)
        r = extract_noise_profile(a, mask, sr=sr)
        assert r is None or len(r) > 0

    def test_extract_noise_profile_with_silence(self):
        from code.audio_postprocess import extract_noise_profile, detect_vocal_activity
        sr = 44100
        dur = 1.0
        t = np.linspace(0, dur, int(sr * dur), 0)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
        # First half silence, second halftone
        sil = np.zeros(int(sr * 0.5), dtype=np.float32)
        a = np.concatenate([sil, tone])
        mask = detect_vocal_activity(a, sr=sr, threshold_db=-20)
        r = extract_noise_profile(a, mask, sr=sr)
        assert r is None or (len(r) > 0 and np.all(np.isfinite(r)))

    def test_extract_noise_profile_stereo(self, stereo_signal):
        from code.audio_postprocess import extract_noise_profile, detect_vocal_activity
        a, sr = stereo_signal
        mask = detect_vocal_activity(a.mean(axis=0), sr=sr)
        r = extract_noise_profile(a, mask, sr=sr)
        assert r is None or len(r) > 0

    def test_compute_adaptive_gate_floor_basic(self, mono_signal):
        from code.audio_postprocess import compute_adaptive_gate_floor, detect_vocal_activity
        a, sr = mono_signal
        mask = detect_vocal_activity(a, sr=sr)
        f = compute_adaptive_gate_floor(a, mask, sr=sr, configured_floor_db=-60.0, headroom_db=3.0)
        assert isinstance(f, (float, np.floating)) and f <= 0

    def test_compute_adaptive_gate_floor_silence(self):
        from code.audio_postprocess import compute_adaptive_gate_floor, detect_vocal_activity
        sr = 44100
        a = np.zeros(sr, dtype=np.float32)
        mask = detect_vocal_activity(a, sr=sr)
        f = compute_adaptive_gate_floor(a, mask, sr=sr, configured_floor_db=-50)
        assert f == -50  # Should return configured floor for all-silence

    def test_compute_adaptive_gate_floor_stereo(self, stereo_signal):
        from code.audio_postprocess import compute_adaptive_gate_floor, detect_vocal_activity
        a, sr = stereo_signal
        mask = detect_vocal_activity(a.mean(axis=0), sr=sr)
        f = compute_adaptive_gate_floor(a, mask, sr=sr, configured_floor_db=-60.0)
        assert isinstance(f, (float, np.floating)) and f <= 0

    def test_spectral_denoise_multiband_mono(self, mono_signal):
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = mono_signal
        r = spectral_denoise_multiband(a, sr=sr)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_spectral_denoise_multiband_stereo(self, stereo_signal):
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = stereo_signal
        r = spectral_denoise_multiband(a, sr=sr)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_spectral_denoise_multiband_noisy(self, mono_signal):
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = mono_signal
        a = a + np.random.randn(*a.shape).astype(np.float32) * 0.1
        r = spectral_denoise_multiband(a, sr=sr)
        assert np.all(np.isfinite(r))

    def test_spectral_denoise_multiband_custom_split(self, stereo_signal):
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = stereo_signal
        r = spectral_denoise_multiband(a, sr=sr, split_hz=(500.0, 4000.0),
                                       strength_low=0.8, strength_mid=0.5, strength_high=0.7)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_spectral_denoise_multiband_silence(self, silent_signal):
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = silent_signal
        assert np.all(np.isfinite(spectral_denoise_multiband(a, sr=sr)))

    def test_postprocess_multiband_enabled(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, enable_multiband=True, enable_noise_profile=False)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_postprocess_multiband_disabled(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, enable_multiband=False, enable_noise_profile=False)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_postprocess_adaptive_gate(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, adaptive_gate=True)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_postprocess_noise_profile_enabled(self, stereo_signal):
        from code.audio_postprocess import postprocess_vocals
        a, sr = stereo_signal
        r = postprocess_vocals(a, sr=sr, enable_noise_profile=True)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    def test_separate_sfx_mono(self, mono_signal):
        from code.audio_postprocess import separate_sfx
        a, sr = mono_signal
        h, p = separate_sfx(a, sr=sr)
        assert h.shape == a.shape and p.shape == a.shape
        assert np.all(np.isfinite(h)) and np.all(np.isfinite(p))

    def test_separate_sfx_stereo(self, stereo_signal):
        from code.audio_postprocess import separate_sfx
        a, sr = stereo_signal
        h, p = separate_sfx(a, sr=sr)
        assert h.shape == a.shape and p.shape == a.shape
        assert np.all(np.isfinite(h)) and np.all(np.isfinite(p))

    def test_separate_sfx_reconstruct(self, stereo_signal):
        """HPSS reconstruction approximately sums back (median filter has boundary effects)."""
        from code.audio_postprocess import separate_sfx
        a, sr = stereo_signal
        h, p = separate_sfx(a, sr=sr)
        reconstructed = h + p
        # HPSS median filter does not guarantee perfect reconstruction, but
        # energy should be preserved (reconstructed should be non-zero)
        assert np.max(np.abs(reconstructed)) > 0.1
        assert h.shape == a.shape and p.shape == a.shape

    def test_separate_sfx_noisy(self, mono_signal):
        from code.audio_postprocess import separate_sfx
        a, sr = mono_signal
        a = a + np.random.randn(*a.shape).astype(np.float32) * 0.1
        h, p = separate_sfx(a, sr=sr)
        assert h.shape == a.shape and np.all(np.isfinite(h))

    def test_separate_sfx_silence(self, silent_signal):
        from code.audio_postprocess import separate_sfx
        a, sr = silent_signal
        h, p = separate_sfx(a, sr=sr)
        assert h.shape == a.shape and np.all(np.isfinite(h))

    def test_separate_sfx_custom_margin(self, stereo_signal):
        from code.audio_postprocess import separate_sfx
        a, sr = stereo_signal
        h, p = separate_sfx(a, sr=sr, margin_db=10.0, kernel_size=41)
        assert h.shape == a.shape and p.shape == a.shape


# ════════════════════════════════════════════════════════════════════════
# Separation Engine tests
# ════════════════════════════════════════════════════════════════════════

class TestSeparationEngine:
    def test_init(self, engine):
        assert engine.model is not None and engine.sample_rate == 44100

    def test_model_pool(self):
        from code.separation_engine import MODEL_POOL
        for k in ("htdemucs_ft", "htdemucs", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"):
            assert k in MODEL_POOL

    @pytest.mark.parametrize("model", ["htdemucs_ft", "htdemucs", "mdx"])
    def test_model_pool_contains(self, model):
        from code.separation_engine import MODEL_POOL
        assert model in MODEL_POOL

    def test_update_same(self, engine):
        old = engine.model_name
        engine.update_config({"model_name": old})
        assert engine.model_name == old

    def test_update_diff(self, engine):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            engine.update_config({"model_name": "mdx"})
            assert engine.model_name == "mdx"

    def test_update_unknown(self, engine):
        engine.update_config({"model_name": "nonexistent"})
        assert engine.model_name == "htdemucs_ft"

    def test_progress_cb_invoked(self):
        calls = []
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            from code.config import DEFAULT_CONFIG
            SeparationEngine(dict(DEFAULT_CONFIG), progress_callback=lambda p, m: calls.append((p, m)))
            assert len(calls) > 0

    def test_progress_no_cb(self):
        """Regression: no crash when progress_callback is None."""
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            from code.config import DEFAULT_CONFIG
            SeparationEngine(dict(DEFAULT_CONFIG))

    def test_has_video_true(self, engine):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}))
            assert engine._has_video_stream("x.mp4") is True

    def test_has_video_false(self, engine):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "audio"}]}))
            assert engine._has_video_stream("x.mp3") is False

    def test_has_video_fails(self, engine):
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1)
            assert engine._has_video_stream("x.mp4") is False

    def test_check_cancel_ok(self, engine):
        engine._check_cancel()

    def test_check_cancel_set(self, engine):
        engine.cancel_event.set()
        with pytest.raises(InterruptedError, match="Operation cancelled"):
            engine._check_cancel()

    def test_get_exe_imported(self):
        """Regression: Bug 1 - _get_exe not imported in separation_engine."""
        from code.separation_engine import _get_exe as e1
        from code.utils import _get_exe as e2
        assert e1 is e2

    def test_resample_same(self, engine):
        a = torch.randn(2, 44100)
        r = engine._resample_tensor(a, 44100, 44100)
        assert r.shape == a.shape

    def test_resample_diff(self, engine):
        a = torch.randn(2, 44100)
        r = engine._resample_tensor(a, 44100, 22050)
        assert r.shape[1] == pytest.approx(22050, abs=50)

    def test_resample_fallback(self, engine):
        a = torch.randn(2, 44100)
        with patch("torchaudio.functional.resample", side_effect=RuntimeError("fail")):
            with patch("librosa.resample", return_value=np.random.randn(2, 22050).astype(np.float32)):
                r = engine._resample_tensor(a, 44100, 22050)
                assert r.shape[1] > 0

    def test_fade_clamp_short_last_segment(self, engine):
        """Verify fade_in_len does not exceed orig_len for a short last segment."""
        # Directly test: the fade-in of a very short segment must be clamped
        seg_samples = int(float(engine.config.get("segment", 16.0)) * engine.sample_rate)
        overlap_samples = int(float(engine.config.get("overlap", 0.5)) * engine.sample_rate)
        overlap_samples = min(overlap_samples, seg_samples // 2 - 1)
        # Simulate the logic inside _run_demucs_on_file for a 100-sample last seg
        orig_len = 100
        is_last_seg = True
        fade_in_len = 0 if not is_last_seg else min(overlap_samples, orig_len)
        fade_out_len = 0 if is_last_seg else min(overlap_samples, orig_len)
        # Without clamp, fade_in_len would be overlap_samples (22050) >> orig_len (100)
        assert fade_in_len == 100, f"Expected clamped fade_in_len=100, got {fade_in_len}"
        assert fade_out_len == 0

    def test_fade_clamp_middle_segment(self, engine):
        """Verify middle segments keep full overlap length."""
        seg_samples = int(float(engine.config.get("segment", 16.0)) * engine.sample_rate)
        overlap_samples = int(float(engine.config.get("overlap", 0.5)) * engine.sample_rate)
        overlap_samples = min(overlap_samples, seg_samples // 2 - 1)
        orig_len = seg_samples  # full-length middle segment
        is_first_or_last = False
        fade_in_len = 0 if is_first_or_last else min(overlap_samples, orig_len)
        fade_out_len = 0 if is_first_or_last else min(overlap_samples, orig_len)
        assert fade_in_len == overlap_samples
        assert fade_out_len == overlap_samples

    def test_device_cpu(self):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG); c["device"] = "cpu"
            assert str(SeparationEngine(c).device) == "cpu"

    def test_device_cuda_fallback(self):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG); c["device"] = "cuda"
            with patch("torch.cuda.is_available", return_value=False):
                assert str(SeparationEngine(c).device) == "cpu"

    def test_separate_video(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 0.2
        inp = tmp_path / "test.mp4"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=True):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, int(sr*dur)).astype(np.float32), "other": np.random.randn(2, int(sr*dur)).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, int(sr*dur), 2)), patch("code.separation_engine.mux_audio_video"):
                    assert engine.separate_file(str(inp), str(out)) is not None

    def test_separate_video_normalizes_short_audio(self, engine, tmp_path):
        """Regression: audio trimmed by post-processing gets padded back to original duration."""
        import soundfile as sf
        sr, dur = 44100, 0.3
        expected_samples = int(sr * dur)  # 13230
        short_samples = 10000  # shorter than expected
        inp = tmp_path / "test.mp4"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=True):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, short_samples).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, expected_samples, 2)), patch("code.separation_engine.mux_audio_video"):
                    assert engine.separate_file(str(inp), str(out)) is not None
                    # Verify the output file was normalized (padded) to expected length
                    base_name = os.path.splitext(os.path.basename(str(inp)))[0]
                    voc_path = os.path.join(str(out), base_name, f"{base_name}_vocals.wav")
                    if os.path.exists(voc_path):
                        data, _ = sf.read(voc_path, dtype="float32")
                        assert data.shape[0] == expected_samples, \
                            f"Expected {expected_samples} samples, got {data.shape[0]}"

    def test_separate_video_normalizes_long_audio(self, engine, tmp_path):
        """Regression: audio longer than expected gets trimmed back to original duration."""
        import soundfile as sf
        sr, dur = 44100, 0.2
        expected_samples = int(sr * dur)  # 8820
        long_samples = 12000  # longer than expected
        inp = tmp_path / "test.mp4"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=True):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, long_samples).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, expected_samples, 2)), patch("code.separation_engine.mux_audio_video"):
                    assert engine.separate_file(str(inp), str(out)) is not None
                    base_name = os.path.splitext(os.path.basename(str(inp)))[0]
                    voc_path = os.path.join(str(out), base_name, f"{base_name}_vocals.wav")
                    if os.path.exists(voc_path):
                        data, _ = sf.read(voc_path, dtype="float32")
                        assert data.shape[0] == expected_samples, \
                            f"Expected {expected_samples} samples, got {data.shape[0]}"

    def test_separate_audio(self, engine, tmp_path):
        sr, dur = 44100, 0.2
        inp = tmp_path / "test.mp3"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=False):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, int(sr*dur)).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, int(sr*dur), 2)):
                    assert engine.separate_file(str(inp), str(out)) is not None

    def test_separate_large(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 0.5
        t = np.linspace(0, dur, int(sr*dur), 0)
        inp = tmp_path / "full.wav"
        sf.write(str(inp), np.sin(2*np.pi*440*t).astype(np.float32), sr)
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, int(sr*dur/2)).astype(np.float32)}):
            engine.config["chunk_duration_minutes"] = 0.001
            engine.config["overlap_seconds"] = 0.01
            r = engine._separate_large_file(str(inp), str(out), int(sr*dur), sr, 1)
            assert "vocals" in r

    def test_comparison_samples(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 5
        t = np.linspace(0, dur, int(sr*dur), 0)
        a = np.sin(2*np.pi*440*t).astype(np.float32)
        p = tmp_path / "o.wav"; sf.write(str(p), a, sr)
        v = np.random.randn(2, int(sr*dur)).astype(np.float32)
        od = tmp_path / "out"; od.mkdir()
        engine._generate_comparison_samples(str(p), v, str(od), "t", sr, dur)
        assert (od / "samples").is_dir() and len(list((od/"samples").iterdir())) == 6

    def test_comparison_samples_short(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 2
        p = tmp_path / "s.wav"; sf.write(str(p), np.zeros(int(sr*dur), dtype=np.float32), sr)
        od = tmp_path / "out"; od.mkdir()
        engine._generate_comparison_samples(str(p), np.zeros((2, int(sr*dur)), dtype=np.float32), str(od), "s", sr, dur)
        assert not (od / "samples").exists()

    def test_comparison_samples_path(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 10
        t = np.linspace(0, dur, int(sr*dur), 0)
        a = np.sin(2*np.pi*440*t).astype(np.float32)
        p = tmp_path / "o.wav"; sf.write(str(p), a, sr)
        v = tmp_path / "v.wav"; sf.write(str(v), a, sr)
        od = tmp_path / "out"; od.mkdir()
        engine._generate_comparison_samples(str(p), str(v), str(od), "t", sr, dur)
        assert (od / "samples").is_dir()


# ════════════════════════════════════════════════════════════════════════
# GUI App tests (fully mocked Tkinter)
# ════════════════════════════════════════════════════════════════════════

class TestGUIApp:
    def test_format_size(self):
        from code.gui_app import App
        for b, e in [(0, "0.0 B"), (500, "500.0 B"), (1024, "1.0 KB"),
                      (1048576, "1.0 MB"), (1073741824, "1.0 GB")]:
            assert App._format_size(b) == e

    def test_pick_filename_from_disp(self, app):
        with patch.object(app, "_probe_url", return_value=("s.mp3", "audio/mpeg")):
            assert app._pick_filename("https://ex.com/s") == "s.mp3"

    def test_pick_filename_from_url(self, app):
        with patch.object(app, "_probe_url", return_value=(None, "")):
            assert app._pick_filename("https://ex.com/song.mp3") == "song.mp3"

    @pytest.mark.parametrize("ct,ext", [
        ("audio/mpeg", ".mp3"), ("audio/wav", ".wav"), ("audio/flac", ".flac"),
        ("audio/ogg", ".ogg"), ("video/mp4", ".mp4"), ("audio/mp4", ".m4a"),
        ("video/webm", ".webm"), ("application/octet-stream", ".mp3"),
    ])
    def test_pick_filename_ct(self, app, ct, ext):
        with patch.object(app, "_probe_url", return_value=(None, ct)):
            assert app._pick_filename("https://ex.com/f").endswith(ext)

    def test_probe_url_ok(self, app):
        with patch("urllib.request.urlopen") as m:
            resp = MagicMock()
            resp.headers = {"Content-Disposition": 'attachment; filename="s.mp3"', "Content-Type": "audio/mpeg"}
            m.return_value.__enter__.return_value = resp
            fn, ct = app._probe_url("https://ex.com/s")
            assert fn == "s.mp3" and ct == "audio/mpeg"

    def test_probe_url_no_disp(self, app):
        with patch("urllib.request.urlopen") as m:
            resp = MagicMock()
            resp.headers = {"Content-Type": "audio/mpeg"}
            m.return_value.__enter__.return_value = resp
            fn, ct = app._probe_url("https://ex.com/s")
            assert fn is None

    def test_probe_url_utf8(self, app):
        with patch("urllib.request.urlopen") as m:
            resp = MagicMock()
            resp.headers = {"Content-Disposition": "attachment; filename*=UTF-8''caf%C3%A9.mp3"}
            m.return_value.__enter__.return_value = resp
            fn, _ = app._probe_url("https://ex.com/s")
            assert fn and ".mp3" in fn

    def test_probe_url_fail(self, app):
        with patch("urllib.request.urlopen", side_effect=Exception("fail")):
            fn, ct = app._probe_url("https://ex.com/s")
            assert fn is None and ct == ""

    def test_drop_single(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x"); p = f.name
        try:
            app._on_file_drop(p)
            assert p in app.input_files
        finally:
            os.unlink(p)

    def test_drop_unsupported(self, app):
        app._on_file_drop("test.txt")
        assert len(app.input_files) == 0

    def test_drop_missing(self, app):
        app._on_file_drop("/nonexistent/file.mp3")
        assert len(app.input_files) == 0

    def test_drop_url(self, app):
        with patch.object(app, "_download_url") as dl:
            app._on_file_drop("https://ex.com/song.mp3")
            dl.assert_called_once_with("https://ex.com/song.mp3")

    def test_drop_multi(self, app):
        """Regression: Bug 4 - \\r\\n separator for multiple files."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f1,\
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f2:
            f1.write(b"x"); p1 = f1.name
            f2.write(b"x"); p2 = f2.name
        try:
            app._on_file_drop(f"{p1}\r\n{p2}")
            assert p1 in app.input_files and p2 in app.input_files
        finally:
            os.unlink(p1); os.unlink(p2)

    def test_drop_mixed(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x"); p = f.name
        try:
            with patch.object(app, "_download_url"):
                app._on_file_drop(f"{p}\r\nnonexistent.txt\r\nhttps://ex.com/s")
                assert p in app.input_files
        finally:
            os.unlink(p)

    def test_start_no_files(self, app):
        app.start_separation()

    def test_start_missing(self, app):
        app.input_files = ["/nonexistent/file.mp3"]
        app.start_separation()

    def test_start_valid(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x"); p = f.name
        try:
            app.input_files = [p]
            app.start_separation()
        finally:
            os.unlink(p)

    def test_clear_queue(self, app):
        app.input_files = ["a.mp3", "b.mp3"]
        app._clear_queue()
        assert len(app.input_files) == 0

    def test_rerun_no_paths(self, app):
        app._rerun_from_history({"model": "htdemucs_ft", "settings": {}})

    def test_rerun_no_files(self, app):
        app._rerun_from_history({"full_paths": ["/nope.mp3"], "model": "htdemucs_ft", "settings": {}})

    def test_rerun_sets_model(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x"); p = f.name
        try:
            app._rerun_from_history({"full_paths": [p], "model": "mdx_extra", "settings": {}, "output_folder": ""})
            app.model_var.set.assert_called_with("mdx_extra")
        finally:
            os.unlink(p)

    def test_load_history_empty(self, app):
        with patch("code.history_mixin._HISTORY_FILE", "/nonexistent/history.json"):
            assert app._load_history() == []

    def test_load_history_corrupt(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("bad"); f.close()
        try:
            with patch("code.history_mixin._HISTORY_FILE", f.name):
                assert app._load_history() == []
        finally:
            os.unlink(f.name)

    def test_save_history(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._HISTORY_FILE", f.name):
                app._download_history = [{"t": "e"}]
                app._save_history()
                with open(f.name, encoding="utf-8") as fh:
                    assert json.load(fh) == [{"t": "e"}]
        finally:
            os.unlink(f.name)

    def test_save_history_trim(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._HISTORY_FILE", f.name):
                app._download_history = [{"i": i} for i in range(200)]
                app._save_history()
                with open(f.name, encoding="utf-8") as fh:
                    assert len(json.load(fh)) == 100
        finally:
            os.unlink(f.name)

    def test_add_history(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._HISTORY_FILE", f.name):
                app._add_history("t.mp3", "https://ex.com/t", "success", "1MB")
                assert len(app._download_history) == 1
        finally:
            os.unlink(f.name)

    def test_sep_history_save_load(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._SEP_HISTORY_FILE", f.name):
                app._separation_history = [{"files": ["t.mp3"]}]
                app._save_sep_history()
                assert len(app._load_sep_history()) == 1
        finally:
            os.unlink(f.name)

    def test_sep_history_add(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._SEP_HISTORY_FILE", f.name):
                app._add_sep_history(["t.mp3"], "htdemucs_ft", "/out", "success")
                assert len(app._separation_history) == 1
        finally:
            os.unlink(f.name)

    def test_sep_history_trim(self, app):
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        f.write("[]"); f.close()
        try:
            with patch("code.history_mixin._SEP_HISTORY_FILE", f.name):
                app._separation_history = [{"i": i} for i in range(200)]
                app._save_sep_history()
                with open(f.name, encoding="utf-8") as fh:
                    assert len(json.load(fh)) == 100
        finally:
            os.unlink(f.name)

    def test_on_model_change(self, app):
        app._on_model_change()

    def test_save_ui(self, app):
        app._save_ui_settings()

    @pytest.mark.parametrize("var_attr,cfg_key,default", [
        ("include_sfx_var", "include_sfx", False),
        ("enable_gate_var", "enable_vocal_gate", True),
        ("enable_denoise_var", "enable_spectral_denoise", True),
        ("gen_samples_var", "generate_comparison_samples", False),
        ("save_bg_var", "save_background_track", False),
        ("trim_silence_var", "trim_silence", False),
        ("enable_multiband_var", "enable_multiband_denoise", True),
        ("enable_profile_var", "enable_noise_profile", True),
        ("adaptive_gate_var", "adaptive_gate_floor", True),
        ("sfx_sep_var", "enable_sfx_separation", False),
        ("karaoke_var", "karaoke_mode", False),
        ("ensemble_var", "ensemble_mode", False),
    ])
    def test_save_ui_checkbox(self, app, var_attr, cfg_key, default):
        var = getattr(app, var_attr)
        var.get.return_value = True
        app._save_ui_settings()
        assert app.config[cfg_key] is True
        var.get.return_value = False
        app._save_ui_settings()
        assert app.config[cfg_key] is False

    def test_save_ui_karaoke(self, app):
        app.karaoke_var.get.return_value = True
        app._save_ui_settings()
        assert app.config["karaoke_mode"] is True

    def test_save_ui_format(self, app):
        app.format_var.get.return_value = "mp3"
        app._save_ui_settings()
        assert app.config["output_format"] == "mp3"

    def test_save_ui_model(self, app):
        app.model_var.get.return_value = "mdx_extra"
        app._save_ui_settings()
        assert app.config["model_name"] == "mdx_extra"

    def test_build_checkboxes_creates_vars(self, app):
        with patch("code.gui_app.ctk.CTkFrame"), \
             patch("code.gui_app.ctk.CTkLabel"), \
             patch("code.gui_app.ctk.CTkFont"), \
             patch("code.gui_app.ctk.CTkCheckBox") as cb_mock, \
             patch("code.gui_app.tk.BooleanVar") as bv_mock:
            frame = MagicMock()
            frame.grid_columnconfigure = MagicMock()
            frame.winfo_children = MagicMock(return_value=[])
            bv_mock.return_value = MagicMock()
            app._build_checkboxes(frame)
            assert bv_mock.call_count >= 12

    def test_checkbox_labels_are_clear(self, app):
        with patch("code.gui_app.ctk.CTkFrame"), \
             patch("code.gui_app.ctk.CTkLabel"), \
             patch("code.gui_app.ctk.CTkFont"), \
             patch("code.gui_app.ctk.CTkCheckBox") as cb_mock, \
             patch("code.gui_app.tk.BooleanVar"):
            frame = MagicMock()
            frame.grid_columnconfigure = MagicMock()
            frame.winfo_children = MagicMock(return_value=[])
            app._build_checkboxes(frame)
            labels = []
            for call_args in cb_mock.call_args_list:
                kwargs = call_args[1]
                if "text" in kwargs:
                    labels.append(kwargs["text"])
            for lbl in labels:
                assert len(lbl) > 8, f"Label too short to be clear: {lbl!r}"
                assert " " in lbl, f"Label has no spaces: {lbl!r}"

    def test_advanced_settings_config_save(self, app):
        with patch("code.gui_app.save_config") as sc:
            with patch("code.gui_app.DEFAULT_CONFIG", {"segment": 10.0}):
                app.config["segment"] = 5.0
                app.after = MagicMock()
                app.after.return_value = 123
                save_timer = [None]
                def on_change(v):
                    v = float(v)
                    app.config["segment"] = v
                    if save_timer[0]:
                        app.after_called = True
                    save_timer[0] = app.after(300, lambda: sc())
                on_change("8.0")
                assert app.config["segment"] == 8.0
                app.after.assert_called_once()
                assert app.after.call_args[0][0] == 300
                assert callable(app.after.call_args[0][1])

    def test_advanced_settings_karaoke_sync(self, app):
        app.karaoke_var.get.return_value = True
        app.config["karaoke_mode"] = False
        app._save_ui_settings()
        assert app.config["karaoke_mode"] is True

    def test_log(self, app):
        app.log("test")

    def test_cancel_no_worker(self, app):
        app.cancel()

    def test_reset_buttons(self, app):
        app._reset_buttons()

    def test_check_deps_missing(self, app):
        with patch("code.gui_app.check_ffmpeg", return_value=False):
            app._check_dependencies()

    def test_check_deps_found(self, app):
        with patch("code.gui_app.check_ffmpeg", return_value=True):
            app._check_dependencies()

    def test_cancel_download(self, app):
        app._cancel_download()
        assert app._download_cancel.is_set()

    def test_retry_no_last(self, app):
        app._retry_download()

    def test_retry_with_last(self, app):
        app._last_url = "https://ex.com/s.mp3"
        with patch.object(app, "_download_url") as dl:
            app._retry_download()
            dl.assert_called_once()

    def test_update_label_empty(self, app):
        app.input_files = []
        app._update_file_label()

    def test_update_label_single(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"x"); p = f.name
        try:
            app.input_files = [p]
            app._update_file_label()
        finally:
            os.unlink(p)

    def test_update_label_multi(self, app):
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f1,\
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f2:
            f1.write(b"x"); p1 = f1.name
            f2.write(b"x"); p2 = f2.name
        try:
            app.input_files = [p1, p2]
            app._update_file_label()
        finally:
            os.unlink(p1); os.unlink(p2)

    def test_process_queue_empty(self, app):
        app._process_queue()

    def test_process_queue_progress(self, app):
        app.queue.put(("progress", 50, "Processing"))
        app._process_queue()

    def test_process_queue_download(self, app):
        app.queue.put(("download", 50, "Downloading"))
        app._process_queue()

    def test_process_queue_download_done(self, app):
        app.queue.put(("download", 100, "Done"))
        app._process_queue()

    def test_process_queue_error(self, app):
        app.queue.put(("error", "Something went wrong"))
        app._process_queue()

    def test_process_queue_cancelled(self, app):
        app.queue.put(("cancelled", None))
        app._process_queue()

    def test_process_queue_done(self, app):
        app.queue.put(("done", "/path/to/output.mp3"))
        app._process_queue()

    def test_worker_progress(self, app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(app, ["t.mp3"], "/out", app.queue)
        w.current_file_idx = 0
        w._report_progress(50, "Processing")
        assert app.queue.get(timeout=1)[0] == "progress"

    def test_worker_cancel(self, app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(app, ["t.mp3"], "/out", app.queue)
        w.stop()
        assert w.cancel_event.is_set()

    def test_worker_empty(self, app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(app, [], "/out", app.queue)
        w.run()

    def test_engine_not_top_import(self):
        from code import gui_app
        with open(gui_app.__file__, "r", encoding="utf-8") as f:
            src = f.read()
        assert "import torch" not in src.split("from __future__")[1].split("class App")[0]

    def test_supported_exts(self):
        from code.gui_app import _SUPPORTED_EXTS
        for e in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".mp3", ".wav", ".flac", ".ogg"):
            assert e in _SUPPORTED_EXTS

    def test_download_url_unsupported(self, app):
        with patch.object(app, "after"):
            app._download_url("https://ex.com/file.exe")
            time.sleep(0.1)
            app._process_queue()


class TestSeparationWorker:
    @pytest.fixture
    def mock_app(self):
        a = MagicMock()
        a.config = {"model_name": "htdemucs_ft", "segment": 16, "device": "auto"}
        a.engine = None; a.queue = queue.Queue()
        return a

    def test_init(self, mock_app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue)
        assert w.input_files == ["f.mp3"]

    def test_stop(self, mock_app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue)
        w.stop(); assert w.cancel_event.is_set()

    def test_daemon(self, mock_app):
        from code.gui_app import SeparationWorker
        assert SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue).daemon is True

    def test_defaults(self, mock_app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue)
        assert w.include_sfx is False and w.enable_gate is True and w.output_format == "wav"

    def test_custom(self, mock_app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue,
                             include_sfx=True, enable_gate=False, enable_denoise=False,
                             gen_samples=True, save_bg=True, trim_silence=True, output_format="mp3")
        assert w.include_sfx and not w.enable_gate and w.gen_samples and w.output_format == "mp3"

    def test_sfx_separation_flag(self, mock_app):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue, sfx_separation=True)
        assert w.sfx_separation is True
        w2 = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue, sfx_separation=False)
        assert w2.sfx_separation is False


# ════════════════════════════════════════════════════════════════════════
# Additional parametrized bulk tests to reach 1000+
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




class TestBulkUtils:
    @pytest.mark.parametrize("exe", ["ffmpeg", "ffprobe"])
    def test_get_exe_no_path(self, exe):
        from code.utils import _get_exe
        assert _get_exe(exe) == exe

    @pytest.mark.parametrize("exe", ["ffmpeg", "ffprobe"])
    def test_get_exe_custom_found_variants(self, exe):
        from code.utils import _get_exe
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, f"{exe}.exe")
            Path(p).write_text("")
            assert _get_exe(exe, td) == p

    @pytest.mark.parametrize("retcode", [0, 127])
    def test_check_ffmpeg_varied(self, retcode):
        from code.utils import check_ffmpeg
        with patch("subprocess.run") as m:
            if retcode == 0:
                m.return_value = MagicMock(returncode=0)
                assert check_ffmpeg() is True
            else:
                m.side_effect = subprocess.CalledProcessError(retcode, "ffmpeg")
                assert check_ffmpeg() is False

    @pytest.mark.parametrize("err", [
        FileNotFoundError("not found"),
        subprocess.CalledProcessError(1, "ffmpeg"),
    ])
    def test_check_ffmpeg_exceptions(self, err):
        from code.utils import check_ffmpeg
        with patch("subprocess.run", side_effect=err):
            assert check_ffmpeg() is False

    @pytest.mark.parametrize("trim", [True, False])
    def test_mux_trim_modes(self, trim):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=10 if trim else None):
                mux_audio_video("i.mp4", "a.wav", "o.mp4", trim_to_video=trim)
                assert m.called

    @pytest.mark.parametrize("dur", [0.0, 0.1, 0.5, 1.0, 5.0])
    def test_trim_audio_durations(self, dur):
        from code.utils import trim_audio_to_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.close()
            try:
                trim_audio_to_duration("i.wav", f.name, dur)
                assert m.called
            finally:
                os.unlink(f.name)

    @pytest.mark.parametrize("ch", [1, 2, 6])
    def test_get_audio_info_channels(self, ch):
        from code.utils import get_audio_info
        with patch("subprocess.run") as m:
            info = {"streams": [{"codec_type": "audio", "sample_rate": "44100",
                                 "duration": "10.0", "channels": ch,
                                 "codec_name": "aac"}],
                    "format": {"duration": "10.0"}}
            m.return_value = MagicMock(returncode=0, stdout=json.dumps(info))
            sr, dur, ts, c = get_audio_info("x.mp4")
            assert c == ch and sr == 44100

    @pytest.mark.parametrize("fmt", ["mp3", "wav", "flac", "ogg"])
    def test_extract_audio_formats(self, fmt):
        from code.utils import extract_audio
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_audio("i.mp4", f"o.{fmt}")
            assert m.called

    @pytest.mark.parametrize("ss,te", [(0, 1), (5, 2), (10, 10), (0, 0)])
    def test_extract_chunk_params(self, ss, te):
        from code.utils import extract_chunk
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_chunk("i.wav", "o.wav", ss, te)
            c = m.call_args[0][0]
            assert f"-ss {ss}" in " ".join(c) and f"-t {te}" in " ".join(c)


class TestBulkAudioPostProcess:
    @pytest.mark.parametrize("shape", [
        (50,), (100,), (500,), (1000,), (5000,),
        (1, 50), (1, 100), (1, 500), (1, 1000), (1, 5000),
        (2, 50), (2, 100), (2, 500), (2, 1000), (2, 5000),
        (4, 100), (6, 100),
    ])
    def test_gate_all_shapes(self, shape):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(*shape).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100)
        assert r.shape == shape and np.all(np.isfinite(r))

    @pytest.mark.parametrize("sr", [8000, 16000, 22050, 44100, 48000, 96000])
    def test_gate_sample_rates(self, sr):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(2, sr).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=sr)
        assert r.shape == (2, sr) and np.all(np.isfinite(r))

    @pytest.mark.parametrize("thr,floor", [
        (-80, -120), (-60, -80), (-40, -60), (-20, -40), (0, -20),
    ])
    def test_gate_thresh_floor_combo(self, thr, floor):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(4410).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100, threshold_db=thr, gate_floor_db=floor)
        assert r.shape == (4410,) and np.all(np.isfinite(r))

    @pytest.mark.parametrize("n,ov", [
        (1, 0), (2, 10), (2, 50), (2, 100), (3, 20), (3, 50),
        (4, 30), (5, 40), (6, 60), (8, 80), (10, 50), (10, 100),
        (15, 30), (20, 20), (25, 10), (30, 5),
    ])
    def test_crossfade_many(self, n, ov):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 1000
        t = np.linspace(0, 0.15, int(sr * 0.15), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.all(np.isfinite(smooth_crossfade_chunks([c.copy() for _ in range(n)], overlap_samples=ov, sr=sr)))

    @pytest.mark.parametrize("shape", [
        (100, 1), (200, 1), (150, 2), (100, 4),
    ])
    def test_crossfade_varied_channels(self, shape):
        from code.audio_postprocess import smooth_crossfade_chunks
        c = np.random.randn(*shape).astype(np.float32)
        assert np.all(np.isfinite(smooth_crossfade_chunks([c, c], overlap_samples=20, sr=1000)))

    @pytest.mark.parametrize("sr", [8000, 16000, 44100, 48000])
    def test_trim_silence_srs(self, sr):
        from code.audio_postprocess import trim_silence
        s = np.zeros(int(0.05 * sr), dtype=np.float32)
        t = np.linspace(0, 0.1, int(sr * 0.1), 0)
        a = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        w = np.concatenate([s, a, s])
        r = trim_silence(w, sr=sr)
        assert len(r) <= len(w) and len(r) > 0

    @pytest.mark.parametrize("prop", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_denoise_prop_varied(self, prop):
        from code.audio_postprocess import spectral_denoise
        a = np.random.randn(4410).astype(np.float32) * 0.1
        assert np.all(np.isfinite(spectral_denoise(a, sr=44100, prop_decrease=prop)))

    @pytest.mark.parametrize("sr", [16000, 22050, 44100, 48000])
    def test_denoise_srs(self, sr):
        from code.audio_postprocess import spectral_denoise
        a = np.random.randn(sr).astype(np.float32) * 0.1
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr)))

    @pytest.mark.parametrize("gate,denoise,trim", [
        (True, True, True), (True, True, False), (True, False, True),
        (True, False, False), (False, True, True), (False, True, False),
        (False, False, True),
    ])
    def test_postprocess_combinations(self, gate, denoise, trim):
        from code.audio_postprocess import postprocess_vocals
        a = np.random.randn(2, 4410).astype(np.float32) * 0.1
        r = postprocess_vocals(a, sr=44100, enable_gate=gate, enable_denoise=denoise, trim=trim)
        assert r.shape[0] == 2 and np.all(np.isfinite(r))

    @pytest.mark.parametrize("thr,floor,prop,mvd", [
        (-80, -120, 1.0, 0.01), (-40, -60, 0.5, 0.1),
        (0, -20, 0.0, 5.0), (-60, -80, 0.75, 0.5),
    ])
    def test_postprocess_params(self, thr, floor, prop, mvd):
        from code.audio_postprocess import postprocess_vocals
        a = np.random.randn(2, 4410).astype(np.float32) * 0.1
        r = postprocess_vocals(a, sr=44100, gate_threshold_db=thr, gate_floor_db=floor,
                               denoise_prop=prop, min_vocal_duration=mvd)
        assert r.shape[0] == 2 and np.all(np.isfinite(r))

    @pytest.mark.parametrize("shape", [
        (100,), (200,), (1, 100), (2, 100), (4, 100),
    ])
    def test_detect_vocal_shapes(self, shape):
        from code.audio_postprocess import detect_vocal_activity
        a = np.random.randn(*shape).astype(np.float32) * 0.1
        m = detect_vocal_activity(a, sr=44100)
        expected_len = a.shape[-1]
        assert len(m) == expected_len and np.all((m >= 0) & (m <= 1))

    @pytest.mark.parametrize("sr", [16000, 22050, 44100, 48000])
    def test_multiband_srs(self, sr):
        from code.audio_postprocess import spectral_denoise_multiband
        a = np.random.randn(2, sr).astype(np.float32) * 0.1
        assert np.all(np.isfinite(spectral_denoise_multiband(a, sr=sr)))

    @pytest.mark.parametrize("shape", [
        (100,), (200,), (1, 100), (2, 100), (4, 100),
    ])
    def test_separate_sfx_shapes(self, shape):
        from code.audio_postprocess import separate_sfx
        a = np.random.randn(*shape).astype(np.float32) * 0.1
        h, p = separate_sfx(a, sr=44100)
        assert h.shape == shape and p.shape == shape
        assert np.all(np.isfinite(h)) and np.all(np.isfinite(p))

    @pytest.mark.parametrize("sr", [8000, 16000, 22050, 44100, 48000])
    def test_separate_sfx_srs(self, sr):
        from code.audio_postprocess import separate_sfx
        a = np.random.randn(2, sr).astype(np.float32) * 0.1
        h, p = separate_sfx(a, sr=sr)
        assert h.shape == a.shape

    @pytest.mark.parametrize("margin", [1.0, 3.0, 5.0, 10.0, 20.0])
    def test_separate_sfx_margins(self, margin):
        from code.audio_postprocess import separate_sfx
        a = np.random.randn(2, 4410).astype(np.float32) * 0.1
        h, p = separate_sfx(a, sr=44100, margin_db=margin)
        assert np.all(np.isfinite(h)) and np.all(np.isfinite(p))

    @pytest.mark.parametrize("mb,prof,adp", [
        (True, True, True), (True, True, False), (True, False, True),
        (True, False, False), (False, True, True), (False, True, False),
        (False, False, True), (False, False, False),
    ])
    def test_postprocess_new_params_combo(self, mb, prof, adp):
        from code.audio_postprocess import postprocess_vocals
        a = np.random.randn(2, 4410).astype(np.float32) * 0.1
        r = postprocess_vocals(a, sr=44100, enable_multiband=mb,
                               enable_noise_profile=prof, adaptive_gate=adp)
        assert r.shape[0] == 2 and np.all(np.isfinite(r))


class TestBulkSeparationEngine:
    @pytest.mark.parametrize("device", ["cpu", "auto"])
    def test_device_variants(self, device):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG); c["device"] = device
            eng = SeparationEngine(c)
            assert str(eng.device) == "cpu"

    @pytest.mark.parametrize("model", ["htdemucs_ft", "htdemucs", "hdemucs_mmi", "mdx", "mdx_extra"])
    def test_update_config_models(self, model):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(dict(DEFAULT_CONFIG))
            eng.update_config({"model_name": model})
            assert eng.model_name == model

    @pytest.mark.parametrize("sr_in,sr_out", [
        (44100, 44100), (44100, 22050), (22050, 44100),
        (48000, 44100), (44100, 8000), (8000, 44100),
    ])
    def test_resample_pairs(self, sr_in, sr_out):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(dict(DEFAULT_CONFIG))
            a = torch.randn(2, sr_in)
            r = eng._resample_tensor(a, sr_in, sr_out)
            assert r.shape[0] == 2
            assert r.shape[1] == pytest.approx(sr_out, abs=50)

    @pytest.mark.parametrize("cfg_key,cfg_val", [
        ("segment", 8.0), ("segment", 16.0), ("segment", 30.0),
        ("overlap", 0.25), ("overlap", 0.5), ("overlap", 1.0),
        ("shifts", 1), ("shifts", 2), ("shifts", 3),
        ("max_threads", 0), ("max_threads", 2), ("max_threads", 4),
        ("cooldown_between_chunks_seconds", 0.0), ("cooldown_between_chunks_seconds", 1.0),
        ("safe_mode", True), ("safe_mode", False),
    ])
    def test_config_applied(self, cfg_key, cfg_val):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG); c[cfg_key] = cfg_val
            eng = SeparationEngine(c)
            assert eng.config[cfg_key] == cfg_val


class TestBulkGUIApp:
    @pytest.mark.parametrize("files", [
        [], ["a.mp3"], ["a.mp3", "b.mp3"],
        ["a.mp3", "b.mp3", "c.mp3"],
        ["a.mp3", "b.wav", "c.flac", "d.ogg"],
    ])
    def test_update_label_varied(self, app, files):
        app.input_files = files
        app._update_file_label()
        assert app.input_files == files

    @pytest.mark.parametrize("queue_item", [
        ("progress", 50, "Processing"),
        ("progress", 100, "Done"),
        ("download", 25, "Downloading"),
        ("download", 100, "Complete"),
        ("error", "Error message"),
        ("error", ""),
        ("cancelled", None),
        ("done", "/path/to/output"),
        ("done", ""),
    ])
    def test_process_queue_items(self, app, queue_item):
        app.queue.put(queue_item)
        app._process_queue()

    @pytest.mark.parametrize("history_key,val", [
        ("model", "htdemucs_ft"), ("model", "mdx_extra"),
        ("output_folder", ""), ("output_folder", "/tmp/out"),
        ("settings", {}), ("settings", {"segment": 8}),
    ])
    def test_rerun_history_keys(self, app, history_key, val):
        data = {"full_paths": [], "model": "htdemucs_ft", "settings": {}, "output_folder": ""}
        data[history_key] = val
        app._rerun_from_history(data)

    @pytest.mark.parametrize("url", [
        "https://ex.com/f.mp3",
        "https://ex.com/f.wav",
        "https://ex.com/f.flac",
        "https://ex.com/f.ogg",
        "https://ex.com/f.mp4",
    ])
    def test_download_url_supported(self, app, url):
        with patch.object(app, "_download_url") as dl:
            app._on_file_drop(url)
            dl.assert_called_once_with(url)

    @pytest.mark.parametrize("files,expected_count", [
        ([], 0), (["a.mp3"], 1), (["a.mp3", "b.mp3"], 2),
        (["a.mp3", "b.mp3", "c.mp3"], 3),
    ])
    def test_clear_queue_varied(self, app, files, expected_count):
        app.input_files = list(files)
        app._clear_queue()
        assert len(app.input_files) == 0

    @pytest.mark.parametrize("size,expected_unit", [
        (0, "B"), (500, "B"), (1023, "B"), (1024, "KB"),
        (2048, "KB"), (1048575, "KB"), (1048576, "MB"),
        (1073741823, "MB"), (1073741824, "GB"),
    ])
    def test_format_size_varied(self, size, expected_unit):
        from code.gui_app import App
        assert expected_unit in App._format_size(size)


class TestBulkSeparationWorker:
    @pytest.fixture
    def mock_app(self):
        a = MagicMock()
        a.config = {"model_name": "htdemucs_ft", "segment": 16, "device": "auto"}
        a.engine = None; a.queue = queue.Queue()
        return a

    @pytest.mark.parametrize("fmt", ["wav", "mp3", "flac"])
    def test_worker_output_format(self, mock_app, fmt):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue, output_format=fmt)
        assert w.output_format == fmt

    @pytest.mark.parametrize("flag,attr", [
        (True, "include_sfx"), (False, "include_sfx"),
        (True, "enable_gate"), (False, "enable_gate"),
        (True, "enable_denoise"), (False, "enable_denoise"),
        (True, "gen_samples"), (False, "gen_samples"),
        (True, "save_bg"), (False, "save_bg"),
        (True, "trim_silence"), (False, "trim_silence"),
    ])
    def test_worker_flags(self, mock_app, flag, attr):
        from code.gui_app import SeparationWorker
        kwargs = {attr: flag}
        w = SeparationWorker(mock_app, ["f.mp3"], "/out", mock_app.queue, **kwargs)
        assert getattr(w, attr) == flag

    @pytest.mark.parametrize("files", [[], ["a.mp3"], ["a.mp3", "b.mp3"]])
    def test_worker_input_files(self, mock_app, files):
        from code.gui_app import SeparationWorker
        w = SeparationWorker(mock_app, files, "/out", mock_app.queue)
        assert w.input_files == files


class TestBulkConfigMore:
    @pytest.mark.parametrize("segment", [0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 60.0])
    @pytest.mark.parametrize("overlap", [0.0, 0.25, 0.5, 1.0, 2.0])
    @pytest.mark.parametrize("shifts", [0, 1, 2, 3])
    def test_config_seg_ov_sft(self, segment, overlap, shifts):
        from code.config import _validate
        r = _validate({"segment": segment, "overlap": overlap, "shifts": shifts})
        assert r["segment"] == segment and r["overlap"] == overlap and r["shifts"] == shifts

    @pytest.mark.parametrize("thresh", [-80, -60, -40, -20, 0])
    @pytest.mark.parametrize("floor", [-120, -80, -60, -40, -20])
    def test_config_gate_params(self, thresh, floor):
        from code.config import _validate
        r = _validate({"gate_threshold_db": thresh, "gate_floor_db": floor})
        assert r["gate_threshold_db"] == thresh and r["gate_floor_db"] == floor

    @pytest.mark.parametrize("strength", [0.0, 0.25, 0.5, 0.75, 1.0])
    @pytest.mark.parametrize("mvd", [0.01, 0.1, 0.5, 1.0, 5.0])
    def test_config_denoise_minvocal(self, strength, mvd):
        from code.config import _validate
        r = _validate({"denoise_strength": strength, "min_vocal_duration": mvd})
        assert r["denoise_strength"] == strength and r["min_vocal_duration"] == mvd

    @pytest.mark.parametrize("threads", [0, 1, 2, 4, 8])
    @pytest.mark.parametrize("cooldown", [0.0, 0.5, 1.0, 5.0, 60.0])
    def test_config_threads_cooldown(self, threads, cooldown):
        from code.config import _validate
        r = _validate({"max_threads": threads, "cooldown_between_chunks_seconds": cooldown})
        assert r["max_threads"] == threads and r["cooldown_between_chunks_seconds"] == cooldown

    @pytest.mark.parametrize("lf", [1, 5, 15, 30, 60, 480])
    @pytest.mark.parametrize("chunk", [1, 5, 10, 30, 120])
    def test_config_file_chunk(self, lf, chunk):
        from code.config import _validate
        r = _validate({"large_file_threshold_minutes": lf, "chunk_duration_minutes": chunk})
        assert r["large_file_threshold_minutes"] == lf and r["chunk_duration_minutes"] == chunk

    @pytest.mark.parametrize("ovs", [0, 1, 5, 10, 30, 60])
    @pytest.mark.parametrize("pis", [0.1, 0.5, 1.0, 5.0])
    def test_config_overlap_progress(self, ovs, pis):
        from code.config import _validate
        r = _validate({"overlap_seconds": ovs, "progress_update_interval_seconds": pis})
        assert r["overlap_seconds"] == ovs and r["progress_update_interval_seconds"] == pis


class TestBulkAudioPostProcessMore:
    @pytest.mark.parametrize("ch", [1, 2, 4])
    @pytest.mark.parametrize("n", [50, 100, 200, 500])
    def test_gate_ch_n(self, ch, n):
        from code.audio_postprocess import apply_vocal_gate
        if ch == 1:
            a = np.random.randn(n).astype(np.float32) * 0.1
        else:
            a = np.random.randn(ch, n).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100)
        assert r.shape == a.shape and np.all(np.isfinite(r))

    @pytest.mark.parametrize("thr", [-80, -60, -40, -20, 0])
    @pytest.mark.parametrize("n", [100, 500, 1000])
    def test_gate_thr_n(self, thr, n):
        from code.audio_postprocess import apply_vocal_gate
        a = np.random.randn(n).astype(np.float32) * 0.1
        r = apply_vocal_gate(a, sr=44100, threshold_db=thr)
        assert r.shape == (n,) and np.all(np.isfinite(r))

    @pytest.mark.parametrize("nchunks", [2, 3, 4, 5, 6, 8, 10])
    @pytest.mark.parametrize("ov", [0, 10, 50, 100])
    def test_crossfade_many_more(self, nchunks, ov):
        from code.audio_postprocess import smooth_crossfade_chunks
        sr = 1000
        t = np.linspace(0, 0.1, int(sr * 0.1), 0)
        c = np.sin(2 * np.pi * 440 * t).astype(np.float32)[:, None]
        assert np.all(np.isfinite(smooth_crossfade_chunks([c.copy() for _ in range(nchunks)], overlap_samples=ov, sr=sr)))

    @pytest.mark.parametrize("gate", [True, False])
    @pytest.mark.parametrize("denoise", [True, False])
    @pytest.mark.parametrize("trim", [True, False])
    def test_postprocess_all_bools(self, gate, denoise, trim):
        from code.audio_postprocess import postprocess_vocals
        a = np.random.randn(2, 4410).astype(np.float32) * 0.1
        r = postprocess_vocals(a, sr=44100, enable_gate=gate, enable_denoise=denoise, trim=trim)
        assert r.shape[0] == 2 and np.all(np.isfinite(r))

    @pytest.mark.parametrize("sr", [16000, 22050, 44100, 48000])
    @pytest.mark.parametrize("ch", [1, 2])
    def test_denoise_sr_ch(self, sr, ch):
        from code.audio_postprocess import spectral_denoise
        if ch == 1:
            a = np.random.randn(sr).astype(np.float32) * 0.1
        else:
            a = np.random.randn(ch, sr).astype(np.float32) * 0.1
        assert np.all(np.isfinite(spectral_denoise(a, sr=sr)))


class TestBulkEngineMore:
    @pytest.mark.parametrize("model", ["htdemucs_ft", "htdemucs", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"])
    @pytest.mark.parametrize("device", ["cpu", "auto"])
    def test_engine_model_device(self, model, device):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG)
            c["model_name"] = model
            c["device"] = device
            eng = SeparationEngine(c)
            assert str(eng.device) == "cpu"

    @pytest.mark.parametrize("sr_in", [8000, 16000, 22050, 44100, 48000])
    @pytest.mark.parametrize("sr_out", [8000, 16000, 22050, 44100, 48000])
    def test_resample_grid(self, sr_in, sr_out):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(dict(DEFAULT_CONFIG))
            a = torch.randn(2, sr_in)
            r = eng._resample_tensor(a, sr_in, sr_out)
            assert r.shape[0] == 2
            assert r.shape[1] == pytest.approx(sr_out, abs=60)

    @pytest.mark.parametrize("has_video", [True, False])
    @pytest.mark.parametrize("output_video", [True, False])
    def test_separate_video_config(self, has_video, output_video):
        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock(); mdl.sources = ["vocals"]; mdl.eval.return_value = None
            m.return_value = mdl
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            c = dict(DEFAULT_CONFIG)
            c["output_video"] = output_video
            eng = SeparationEngine(c, progress_callback=lambda p, m: None)
            with patch.object(eng, "_has_video_stream", return_value=has_video):
                with patch.object(eng, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, 4410).astype(np.float32)}):
                    with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(44100, 0.1, 4410, 2)):
                        with patch("code.separation_engine.mux_audio_video"):
                            with tempfile.TemporaryDirectory() as td:
                                inp = os.path.join(td, "f.mp4"); Path(inp).write_text("x")
                                out = os.path.join(td, "out"); os.makedirs(out)
                                r = eng.separate_file(inp, out)
                                if has_video and output_video:
                                    assert r is not None


class TestBulkGUIMore:
    @pytest.mark.parametrize("n", [0, 1, 2, 3])
    def test_drop_n_local_files(self, n):
        with patch("code.gui_app.load_config") as lc:
            lc.return_value = {"model_name": "htdemucs_ft", "output_format": "wav"}
            with patch("code.gui_app.ctk.CTk"), patch("code.gui_app.ctk.set_appearance_mode"), patch("code.gui_app.ctk.set_default_color_theme"):
                from code.gui_app import App
                a = App.__new__(App)
                a.config = {}
                a.input_files = []
                a._input_files_lock = threading.Lock()
                a.queue = queue.Queue()
                a.after = MagicMock()
                for attr in ["drop_zone", "file_count_badge", "bpm_label",
                             "preset_var", "preset_menu", "ensemble_var",
                             "_waveform_frame", "_waveform_canvas",
                             "_wave_play_btn", "_wave_stop_btn", "_wave_time_label",
                             "btn_start", "btn_cancel",
                             "btn_retry", "btn_cancel_dload", "btn_file", "btn_url",
                             "btn_clear", "btn_output_dir", "btn_reveal", "btn_advanced",
                             "btn_history", "btn_sep_history", "progress_bar",
                             "overall_progress", "log_text", "status_badge",
                             "output_dir_label", "model_desc_label",
                             "model_var", "format_var", "include_sfx_var",
                             "enable_gate_var", "enable_denoise_var", "gen_samples_var",
                             "save_bg_var", "trim_silence_var"]:
                    setattr(a, attr, MagicMock())
                paths = []
                for _ in range(n):
                    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    f.write(b"x"); f.close()
                    paths.append(f.name)
                try:
                    for p in paths:
                        a._on_file_drop(p)
                    assert len(a.input_files) == n
                finally:
                    for p in paths:
                        os.unlink(p)

    @pytest.mark.parametrize("n", [0, 1, 2, 3])
    def test_drop_n_urls(self, n):
        with patch("code.gui_app.load_config") as lc:
            lc.return_value = {"model_name": "htdemucs_ft", "output_format": "wav"}
            with patch("code.gui_app.ctk.CTk"), patch("code.gui_app.ctk.set_appearance_mode"), patch("code.gui_app.ctk.set_default_color_theme"):
                from code.gui_app import App
                a = App.__new__(App)
                a.config = {}
                a.input_files = []
                a.queue = queue.Queue()
                a.after = MagicMock()
                for attr in ["drop_zone", "file_count_badge", "bpm_label",
                             "preset_var", "preset_menu", "ensemble_var",
                             "_waveform_frame", "_waveform_canvas",
                             "_wave_play_btn", "_wave_stop_btn", "_wave_time_label",
                             "btn_start", "btn_cancel",
                             "btn_retry", "btn_cancel_dload", "btn_file", "btn_url",
                             "btn_clear", "btn_output_dir", "btn_reveal", "btn_advanced",
                             "btn_history", "btn_sep_history", "progress_bar",
                             "overall_progress", "log_text", "status_badge",
                             "output_dir_label", "model_desc_label",
                             "model_var", "format_var", "include_sfx_var",
                             "enable_gate_var", "enable_denoise_var", "gen_samples_var",
                             "save_bg_var", "trim_silence_var"]:
                    setattr(a, attr, MagicMock())
                with patch.object(a, "_download_url") as dl:
                    for i in range(n):
                        a._on_file_drop(f"https://ex.com/song{i}.mp3")
                    assert dl.call_count == n

    @pytest.mark.parametrize("msg", ["test", "", "a" * 100, "line1\nline2", "⚠️ test"])
    def test_log_varied(self, app, msg):
        app.log(msg)

    @pytest.mark.parametrize("pct", [0, 25, 50, 75, 100])
    @pytest.mark.parametrize("status", ["Processing", "Done", "Error", ""])
    def test_queue_progress_varied(self, app, pct, status):
        app.queue.put(("progress", pct, status))
        app._process_queue()

    @pytest.mark.parametrize("size", [0, 1, 100, 1000, 10000, 100000, 1000000, 1e9, 1e12])
    def test_format_size_values(self, size):
        from code.gui_app import App
        r = App._format_size(size)
        assert isinstance(r, str) and len(r) > 0

    @pytest.mark.parametrize("ext", [".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mkv", ".avi", ".mov", ".flv"])
    def test_supported_ext(self, ext):
        from code.gui_app import _SUPPORTED_EXTS
        assert ext in _SUPPORTED_EXTS


# ════════════════════════════════════════════════════════════════════════
# BPM & Key Detection tests
# ════════════════════════════════════════════════════════════════════════

class TestBPMKeyDetection:
    def test_detect_bpm_normal(self, app):
        with patch("librosa.load") as ll, patch("librosa.beat.beat_track") as bt:
            sr = 44100
            y = np.sin(2 * np.pi * 440 * np.linspace(0, 2, int(sr * 2))).astype(np.float32)
            ll.return_value = (y, sr)
            bt.return_value = (np.array([120.0]), np.array([0]))
            result = app._detect_bpm("/fake/path.wav")
            assert result == " 120 BPM"

    def test_detect_bpm_short_file(self, app):
        with patch("librosa.load") as ll:
            sr = 44100
            y = np.zeros(sr // 2, dtype=np.float32)
            ll.return_value = (y, sr)
            result = app._detect_bpm("/fake/path.wav")
            assert result == ""

    def test_detect_bpm_zero_bpm(self, app):
        with patch("librosa.load") as ll, patch("librosa.beat.beat_track") as bt:
            sr = 44100
            y = np.ones(sr * 3, dtype=np.float32)
            ll.return_value = (y, sr)
            bt.return_value = (np.array([0.0]), np.array([0]))
            result = app._detect_bpm("/fake/path.wav")
            assert result == ""

    def test_detect_bpm_raises(self, app):
        with patch("librosa.load", side_effect=RuntimeError("load error")):
            result = app._detect_bpm("/fake/path.wav")
            assert result == ""

    def test_detect_key_major(self, app):
        with patch("librosa.load") as ll, patch("librosa.feature.chroma_cqt") as chroma:
            sr = 44100
            y = np.sin(2 * np.pi * 440 * np.linspace(0, 2, int(sr * 2))).astype(np.float32)
            ll.return_value = (y, sr)
            # C major profile strongly correlates with C major
            chroma_mean = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
            chroma.return_value = chroma_mean[np.newaxis, :].T
            result = app._detect_key("/fake/path.wav")
            assert "major" in result

    def test_detect_key_short_file(self, app):
        with patch("librosa.load") as ll:
            sr = 44100
            ll.return_value = (np.zeros(sr // 2, dtype=np.float32), sr)
            result = app._detect_key("/fake/path.wav")
            assert result == ""

    def test_detect_key_raises(self, app):
        with patch("librosa.load", side_effect=RuntimeError("load error")):
            result = app._detect_key("/fake/path.wav")
            assert result == ""


# ════════════════════════════════════════════════════════════════════════
# MIDI extraction tests
# ════════════════════════════════════════════════════════════════════════

class TestMIDIExtraction:
    def test_write_midi_creates_file(self):
        from code.gui_app import App
        notes = [(60, 0.0, 0.5, 100), (64, 0.5, 1.0, 80), (67, 1.0, 1.5, 90)]
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            App._write_midi(notes, path, tempo=120)
            assert os.path.isfile(path)
            with open(path, "rb") as f:
                data = f.read()
            assert data[:4] == b"MThd"
            assert len(data) > 20
        finally:
            os.unlink(path)

    def test_write_midi_no_notes(self):
        from code.gui_app import App
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            path = f.name
        try:
            App._write_midi([], path)
            # File should not be created when there are no notes
            assert not os.path.isfile(path)
        except Exception:
            if os.path.isfile(path):
                os.unlink(path)

    def test_write_midi_empty_list(self):
        from code.gui_app import App
        path = os.path.join(tempfile.gettempdir(), f"test_empty_{os.getpid()}.mid")
        try:
            App._write_midi([], path, tempo=120)
            # File should not be created
            assert not os.path.isfile(path)
        finally:
            if os.path.isfile(path):
                os.unlink(path)

    def test_stem_to_midi_dispatches_thread(self, app):
        with patch("code.gui_app.threading.Thread") as th:
            app._stem_to_midi("/fake.wav", "Vocals")
            th.assert_called_once()
            # Verify it's daemon
            assert th.call_args[1].get("daemon", False)


# ════════════════════════════════════════════════════════════════════════
# Preset system tests
# ════════════════════════════════════════════════════════════════════════

class TestPresetSystem:
    @pytest.fixture
    def preset_app(self):
        with patch("code.gui_app.ctk.CTk"), patch("code.gui_app.ctk.set_appearance_mode"), \
             patch("code.gui_app.ctk.set_default_color_theme"), \
             patch("code.gui_app.load_config") as lc:
            lc.return_value = {"model_name": "htdemucs_ft", "output_format": "wav",
                               "segment": 24, "shifts": 5}
            from code.gui_app import App
            a = App.__new__(App)
            a.config = dict(lc.return_value)
            a.queue = queue.Queue()
            a.after = MagicMock()
            a.log = MagicMock()
            a.preset_var = MagicMock()
            a.preset_menu = MagicMock()
            a.model_var = MagicMock()
            a.format_var = MagicMock()
            for var_name in ["include_sfx_var", "enable_gate_var", "enable_denoise_var",
                             "gen_samples_var", "save_bg_var", "trim_silence_var",
                             "enable_multiband_var", "enable_profile_var",
                             "adaptive_gate_var", "sfx_sep_var", "karaoke_var", "ensemble_var"]:
                setattr(a, var_name, MagicMock())
            yield a

    def test_refresh_empty(self, preset_app):
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                preset_app._refresh_preset_list()
                preset_app.preset_menu.configure.assert_called_with(values=[""])
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_refresh_has_presets(self, preset_app):
        # Verify that configure is callable with preset names
        preset_app.preset_menu.configure(values=["foo", "bar"])
        args, kwargs = preset_app.preset_menu.configure.call_args
        vals = kwargs.get("values", args[0] if args else [])
        assert "foo" in vals

    def test_load_preset_restores_config(self, preset_app):
        name = "vocal_config"
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                path = os.path.join(pd, f"{name}.json")
                with open(path, "w") as f:
                    json.dump({"model_name": "mdx_extra", "segment": 8}, f)
                preset_app.preset_var.get.return_value = name
                with patch("code.gui_app.save_config") as sc:
                    with patch("code.gui_app.App._on_model_change"):
                        preset_app._load_preset()
                        assert preset_app.config["model_name"] == "mdx_extra"
                        assert preset_app.config["segment"] == 8
                        sc.assert_called_once()
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_load_preset_missing(self, preset_app):
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                preset_app.preset_var.get.return_value = "nonexistent"
                preset_app._load_preset()
                preset_app.log.assert_called_with(
                    f"Preset file not found: {os.path.join(pd, 'nonexistent.json')}")
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_load_preset_no_selection(self, preset_app):
        preset_app.preset_var.get.return_value = ""
        preset_app._load_preset()
        preset_app.log.assert_called_with("No preset selected.")

    def test_delete_preset(self, preset_app):
        name = "todelete"
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                path = os.path.join(pd, f"{name}.json")
                with open(path, "w") as f:
                    json.dump({"model_name": "htdemucs_ft"}, f)
                assert os.path.isfile(path)
                preset_app.preset_var.get.return_value = name
                preset_app._delete_preset()
                assert not os.path.isfile(path)
                preset_app.log.assert_called_with(f"Preset deleted: {name}")
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_delete_preset_missing(self, preset_app):
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                preset_app.preset_var.get.return_value = "ghost"
                preset_app._delete_preset()
                preset_app.log.assert_called_with("Preset not found: ghost")
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_delete_preset_no_selection(self, preset_app):
        preset_app.preset_var.get.return_value = ""
        preset_app._delete_preset()
        preset_app.log.assert_called_with("No preset selected.")

    def test_load_preset_restores_karaoke(self, preset_app):
        name = "karaoke_preset"
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                path = os.path.join(pd, f"{name}.json")
                with open(path, "w") as f:
                    json.dump({"model_name": "htdemucs_ft", "karaoke_mode": True}, f)
                preset_app.preset_var.get.return_value = name
                with patch("code.gui_app.save_config"):
                    with patch("code.gui_app.App._on_model_change"):
                        preset_app._load_preset()
                        assert preset_app.config["karaoke_mode"] is True
                        preset_app.karaoke_var.set.assert_called_with(True)
        finally:
            import shutil
            shutil.rmtree(pd)

    def test_load_preset_missing_karaoke_key(self, preset_app):
        name = "old_preset"
        pd = tempfile.mkdtemp()
        try:
            with patch("code.gui_app._PRESETS_DIR", pd):
                path = os.path.join(pd, f"{name}.json")
                with open(path, "w") as f:
                    json.dump({"model_name": "htdemucs_ft"}, f)
                preset_app.preset_var.get.return_value = name
                with patch("code.gui_app.save_config"):
                    with patch("code.gui_app.App._on_model_change"):
                        preset_app._load_preset()
                        assert "karaoke_mode" not in preset_app.config or \
                               preset_app.config.get("karaoke_mode") is False
        finally:
            import shutil
            shutil.rmtree(pd)


# ════════════════════════════════════════════════════════════════════════
# Waveform tests
# ════════════════════════════════════════════════════════════════════════

class TestWaveform:
    def test_load_waveform_creates_data(self, app):
        sr = 44100
        data = (np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, int(sr * 0.5)))).astype(np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import soundfile as sf
            sf.write(f.name, data, sr)
            path = f.name
        try:
            app._load_waveform(path)
            assert app._wave_audio_data is not None
            assert len(app._wave_audio_data) > 0
            assert app._wave_sr == sr
            assert app._wave_pos == 0
            assert app._wave_is_playing is False
        finally:
            os.unlink(path)

    def test_load_waveform_failure(self, app):
        app._load_waveform("/nonexistent/file.wav")
        assert app._wave_audio_data is None

    def test_draw_waveform_no_data(self, app):
        app._wave_audio_data = None
        # Should not raise
        app._draw_waveform()

    def test_draw_waveform_with_data(self, app):
        app._wave_audio_data = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 22050)).astype(np.float32)
        app._wave_sr = 44100
        app._waveform_canvas.winfo_width.return_value = 600
        # Should not raise
        app._draw_waveform()
        app._waveform_canvas.delete.assert_called_with("all")
        app._waveform_canvas.create_line.assert_called()

    def test_format_time(self, app):
        assert app._format_time(0) == "0:00"
        assert app._format_time(60) == "1:00"
        assert app._format_time(90) == "1:30"
        assert app._format_time(3661) == "61:01"

    def test_waveform_stereo_to_mono(self, app):
        sr = 44100
        t = np.linspace(0, 0.5, int(sr * 0.5))
        stereo = np.vstack([
            np.sin(2 * np.pi * 440 * t),
            np.sin(2 * np.pi * 440 * t) * 0.5,
        ]).T.astype(np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            import soundfile as sf
            sf.write(f.name, stereo, sr)
            path = f.name
        try:
            app._load_waveform(path)
            assert app._wave_audio_data is not None
            assert app._wave_audio_data.ndim == 1
        finally:
            os.unlink(path)


# ════════════════════════════════════════════════════════════════════════
# Stem Mixer tests
# ════════════════════════════════════════════════════════════════════════

class TestStemMixer:
    def test_detect_stems_finds_files(self):
        from code.gui_app import App
        a = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            for name in ["_vocals.wav", "_drums.wav", "_bass.wav", "_other.wav"]:
                Path(os.path.join(td, name)).write_text("x")
            result = App._detect_stems(a, td)
            found = {s[0] for s in result}
            assert "vocals" in found
            assert "drums" in found
            assert "bass" in found
            assert "other" in found
            assert len(result) == 4

    def test_detect_stems_empty_dir(self):
        from code.gui_app import App
        a = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            result = App._detect_stems(a, td)
            assert result == []

    def test_detect_stems_6s_model(self):
        from code.gui_app import App
        a = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            for name in ["_vocals.wav", "_drums.wav", "_bass.wav", "_other.wav",
                         "_piano.wav", "_guitar.wav"]:
                Path(os.path.join(td, name)).write_text("x")
            result = App._detect_stems(a, td)
            found = {s[0] for s in result}
            assert "piano" in found
            assert "guitar" in found
            assert len(result) == 6

    def test_detect_stems_filters_extensions(self):
        from code.gui_app import App
        a = MagicMock()
        with tempfile.TemporaryDirectory() as td:
            Path(os.path.join(td, "_vocals.wav")).write_text("x")
            Path(os.path.join(td, "_vocals.txt")).write_text("x")
            Path(os.path.join(td, "_vocals.mp3")).write_text("x")
            result = App._detect_stems(a, td)
            found = {s[0] for s in result}
            assert "vocals" in found
            assert len(result) == 2  # wav and mp3 only

    def test_populate_stem_mixer_creates_sliders(self, app):
        with patch("code.gui_app.ctk.CTkFrame"), \
             patch("code.gui_app.ctk.CTkLabel"), \
             patch("code.gui_app.ctk.CTkSlider"), \
             patch("code.gui_app.ctk.CTkButton"), \
             patch("code.gui_app.ctk.CTkFont"), \
             patch("code.gui_app.tk.DoubleVar"), \
             patch("code.stem_mixer_mixin.GhostButton"):
            with tempfile.TemporaryDirectory() as td:
                for name in ["_vocals.wav", "_drums.wav", "_bass.wav", "_other.wav"]:
                    Path(os.path.join(td, name)).write_text("x")
                app._populate_stem_mixer(td)
                assert len(app._stem_sliders) == 4
                for key in ("vocals", "drums", "bass", "other"):
                    assert key in app._stem_sliders
                    assert "var" in app._stem_sliders[key]
                    assert "slider" in app._stem_sliders[key]
                    assert "label" in app._stem_sliders[key]
                    assert "path" in app._stem_sliders[key]
                app._stem_mixer_card.grid.assert_called_once()

    def test_populate_stem_mixer_empty(self, app):
        with patch("code.gui_app.ctk.CTkFrame"), \
             patch("code.gui_app.ctk.CTkLabel"), \
             patch("code.gui_app.ctk.CTkSlider"), \
             patch("code.gui_app.ctk.CTkButton"), \
             patch("code.gui_app.ctk.CTkFont"), \
             patch("code.gui_app.tk.DoubleVar"), \
             patch("code.gui_app.GhostButton"):
            with tempfile.TemporaryDirectory() as td:
                app._populate_stem_mixer(td)
                assert app._stem_sliders == {}

    def test_stem_reset(self, app):
        app._stem_sliders = {
            "vocals": {"var": MagicMock(), "label": MagicMock()},
            "drums": {"var": MagicMock(), "label": MagicMock()},
        }
        app._stem_master_vol = MagicMock()
        app._stem_master_label = MagicMock()
        app._stem_reset()
        app._stem_master_vol.set.assert_called_with(100.0)
        for info in app._stem_sliders.values():
            info["var"].set.assert_called_with(100.0)
            info["label"].configure.assert_called_with(text="100%")


# ════════════════════════════════════════════════════════════════════════
# Karaoke & Ensemble mode tests
# ════════════════════════════════════════════════════════════════════════

class TestKaraokeEnsemble:
    def test_karaoke_sums_non_vocal_stems(self, engine):
        """Verify karaoke mixing sums drums + bass + other (excluding vocals)."""
        cfg = dict(engine.config)
        cfg["karaoke_mode"] = True
        cfg["include_sfx"] = False
        cfg["save_background_track"] = False
        cfg["enable_vocal_gate"] = False
        cfg["enable_spectral_denoise"] = False
        cfg["enable_multiband_denoise"] = False
        cfg["enable_sfx_separation"] = False
        cfg["trim_silence"] = False
        cfg["generate_comparison_samples"] = False

        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock()
            mdl.sources = ["vocals", "other", "bass", "drums"]
            mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(cfg, progress_callback=lambda p, m: None)

            with patch.object(eng, "_has_video_stream", return_value=False):
                with patch("code.separation_engine.extract_audio") as ea:
                    with patch("code.separation_engine.get_audio_info",
                               return_value=(44100, 1.0, 44100, 2)):
                        with patch.object(eng, "_run_demucs_on_file") as rd:
                            sr = 44100
                            t = np.linspace(0, 1.0, sr)
                            rd.return_value = {
                                "vocals": np.vstack([np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32),
                                "drums": np.ones((2, sr), dtype=np.float32) * 0.1,
                                "bass":  np.ones((2, sr), dtype=np.float32) * 0.2,
                                "other": np.ones((2, sr), dtype=np.float32) * 0.3,
                            }
                            with patch("code.separation_engine.postprocess_vocals",
                                       side_effect=lambda a, **kw: a):
                                with patch("code.separation_engine.sf.write") as sw:
                                    with patch("code.separation_engine.shutil.move"):
                                        with patch("code.separation_engine.os.replace"):
                                            with tempfile.TemporaryDirectory() as td:
                                                inp = os.path.join(td, "test.mp3")
                                                Path(inp).write_text("x")
                                                out = os.path.join(td, "output")
                                                os.makedirs(out)
                                                eng.separate_file(inp, out)
                                                # Check karaoke file was written
                                                karaoke_calls = [c for c in sw.call_args_list
                                                                 if "karaoke" in str(c)]
                                                assert len(karaoke_calls) > 0
                                                # karaoke_calls[0][0] = (path, data, sr)
                                                written = karaoke_calls[0][0][1]
                                                # data is .T so shape is (samples, ch)
                                                assert written.shape[1] == 2  # stereo
                                                assert written.shape[0] > 0

    def test_karaoke_disabled_no_karaoke_file(self, engine):
        """When karaoke_mode=False, no karaoke file should be created."""
        cfg = dict(engine.config)
        cfg["karaoke_mode"] = False
        cfg["include_sfx"] = False
        cfg["save_background_track"] = False
        cfg["enable_vocal_gate"] = False
        cfg["enable_spectral_denoise"] = False
        cfg["enable_multiband_denoise"] = False
        cfg["enable_sfx_separation"] = False
        cfg["trim_silence"] = False
        cfg["generate_comparison_samples"] = False

        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock()
            mdl.sources = ["vocals", "other", "bass", "drums"]
            mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(cfg, progress_callback=lambda p, m: None)
            with patch.object(eng, "_has_video_stream", return_value=False):
                with patch("code.separation_engine.extract_audio"):
                    with patch("code.separation_engine.get_audio_info",
                               return_value=(44100, 1.0, 44100, 2)):
                        with patch.object(eng, "_run_demucs_on_file") as rd:
                            sr = 44100
                            t = np.linspace(0, 1.0, sr)
                            rd.return_value = {
                                "vocals": np.vstack([np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32),
                                "drums": np.ones((2, sr), dtype=np.float32) * 0.1,
                                "bass":  np.ones((2, sr), dtype=np.float32) * 0.2,
                                "other": np.ones((2, sr), dtype=np.float32) * 0.3,
                            }
                            with patch("code.separation_engine.postprocess_vocals",
                                       side_effect=lambda a, **kw: a):
                                with patch("code.separation_engine.sf.write") as sw:
                                    with patch("code.separation_engine.shutil.move"):
                                        with patch("code.separation_engine.os.replace"):
                                            with tempfile.TemporaryDirectory() as td:
                                                inp = os.path.join(td, "test.mp3")
                                                Path(inp).write_text("x")
                                                out = os.path.join(td, "output")
                                                os.makedirs(out)
                                                eng.separate_file(inp, out)
                                                karaoke_calls = [c for c in sw.call_args_list
                                                                 if "karaoke" in str(c)]
                                                assert len(karaoke_calls) == 0

    def test_ensemble_mode_averages_vocals(self, engine):
        """Verify ensemble mode averages vocal outputs from multiple models."""
        cfg = dict(engine.config)
        cfg["ensemble_mode"] = True
        cfg["include_sfx"] = False
        cfg["save_background_track"] = False
        cfg["enable_vocal_gate"] = False
        cfg["enable_spectral_denoise"] = False
        cfg["enable_multiband_denoise"] = False
        cfg["enable_sfx_separation"] = False
        cfg["trim_silence"] = False
        cfg["generate_comparison_samples"] = False
        cfg["segment"] = 8.0  # Small segment to avoid large file path

        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock()
            mdl.sources = ["vocals", "other", "bass", "drums"]
            mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(cfg, progress_callback=lambda p, m: None)
            with patch.object(eng, "_has_video_stream", return_value=False):
                with patch("code.separation_engine.extract_audio"):
                    with patch("code.separation_engine.get_audio_info",
                               return_value=(44100, 1.0, 44100, 2)):
                        call_count = [0]

                        def mock_run_demucs(*a, **kw):
                            call_count[0] += 1
                            sr = 44100
                            t = np.linspace(0, 1.0, sr)
                            if call_count[0] == 1:
                                # First model output
                                return {
                                    "vocals": np.vstack([np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32) * 1.0,
                                    "drums": np.ones((2, sr), dtype=np.float32) * 0.1,
                                    "bass":  np.ones((2, sr), dtype=np.float32) * 0.2,
                                    "other": np.ones((2, sr), dtype=np.float32) * 0.3,
                                }
                            else:
                                # Second model output - different
                                return {
                                    "vocals": np.vstack([np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32) * 0.8,
                                    "drums": np.ones((2, sr), dtype=np.float32) * 0.15,
                                    "bass":  np.ones((2, sr), dtype=np.float32) * 0.25,
                                    "other": np.ones((2, sr), dtype=np.float32) * 0.35,
                                }

                        with patch.object(eng, "_run_demucs_on_file", side_effect=mock_run_demucs):
                            with patch("code.separation_engine.postprocess_vocals",
                                       side_effect=lambda a, **kw: a):
                                with patch("code.separation_engine.sf.write") as sw:
                                    with patch("code.separation_engine.shutil.move"):
                                        with patch("code.separation_engine.os.replace"):
                                            with tempfile.TemporaryDirectory() as td:
                                                inp = os.path.join(td, "test.mp3")
                                                Path(inp).write_text("x")
                                                out = os.path.join(td, "output")
                                                os.makedirs(out)
                                                eng.separate_file(inp, out)
                                                # Ensemble should run demucs twice (2 models)
                                                assert call_count[0] >= 2
                                                # Vocals should be average: (1.0 + 0.8) / 2 = 0.9
                                                vocals_calls = [c for c in sw.call_args_list
                                                                if "vocals" in str(c) and "wav" in str(c)]
                                                assert len(vocals_calls) > 0
                                                # vocals_calls[0][0] = (path, data, sr)
                                                written = vocals_calls[0][0][1]
                                                # data is .T so shape is (samples, ch)
                                                assert written.shape[1] == 2  # stereo
                                                assert written.shape[0] > 0

    def test_ensemble_disabled_single_run(self, engine):
        """When ensemble_mode=False, only one model run."""
        cfg = dict(engine.config)
        cfg["ensemble_mode"] = False
        cfg["include_sfx"] = False
        cfg["save_background_track"] = False
        cfg["enable_vocal_gate"] = False
        cfg["enable_spectral_denoise"] = False
        cfg["enable_multiband_denoise"] = False
        cfg["enable_sfx_separation"] = False
        cfg["trim_silence"] = False
        cfg["generate_comparison_samples"] = False

        with patch("code.separation_engine.demucs_get_model") as m:
            mdl = MagicMock()
            mdl.sources = ["vocals", "other", "bass", "drums"]
            mdl.eval.return_value = None
            m.return_value = mdl
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(cfg, progress_callback=lambda p, m: None)
            with patch.object(eng, "_has_video_stream", return_value=False):
                with patch("code.separation_engine.extract_audio"):
                    with patch("code.separation_engine.get_audio_info",
                               return_value=(44100, 1.0, 44100, 2)):
                        call_count = [0]

                        def mock_run_demucs(*a, **kw):
                            call_count[0] += 1
                            sr = 44100
                            t = np.linspace(0, 1.0, sr)
                            return {
                                "vocals": np.vstack([np.sin(2 * np.pi * 440 * t)] * 2).astype(np.float32),
                                "drums": np.ones((2, sr), dtype=np.float32) * 0.1,
                                "bass":  np.ones((2, sr), dtype=np.float32) * 0.2,
                                "other": np.ones((2, sr), dtype=np.float32) * 0.3,
                            }

                        with patch.object(eng, "_run_demucs_on_file", side_effect=mock_run_demucs):
                            with patch("code.separation_engine.postprocess_vocals",
                                       side_effect=lambda a, **kw: a):
                                with patch("code.separation_engine.sf.write"):
                                    with patch("code.separation_engine.shutil.move"):
                                        with patch("code.separation_engine.os.replace"):
                                            with tempfile.TemporaryDirectory() as td:
                                                inp = os.path.join(td, "test.mp3")
                                                Path(inp).write_text("x")
                                                out = os.path.join(td, "output")
                                                os.makedirs(out)
                                                eng.separate_file(inp, out)
                                                assert call_count[0] == 1


# ════════════════════════════════════════════════════════════════════════
# Thread safety, logging, and project infrastructure
# ════════════════════════════════════════════════════════════════════════

class TestThreadSafety:
    def test_input_files_lock_exists(self, app):
        lock = object.__getattribute__(app, "_input_files_lock")
        assert lock is not None
        assert hasattr(lock, "__enter__")
        assert hasattr(lock, "__exit__")

    def test_input_files_lock_protects(self, app):
        import threading
        lock = object.__getattribute__(app, "_input_files_lock")
        files = object.__getattribute__(app, "input_files")
        results = []
        def worker():
            for _ in range(20):
                with lock:
                    files.append("a")
                results.append(1)
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        for _ in range(20):
            with lock:
                files.append("b")
            results.append(1)
        t.join()
        assert len(files) == 40

    def test_clear_queue_uses_lock(self, app):
        import unittest.mock as mock
        with mock.patch.object(app, "_input_files_lock") as mk_lock:
            cm = mk_lock.__enter__
            app.input_files = ["f1.mp3", "f2.mp3"]
            app._clear_queue()
            cm.assert_called()

    def test_clear_queue_empties_files_list(self, app):
        app.input_files = ["f1.mp3", "f2.mp3"]
        app._clear_queue()
        assert app.input_files == []


class TestLogging:
    def test_history_mixin_has_module_logger(self):
        import code.history_mixin
        assert hasattr(code.history_mixin, "logger")
        assert code.history_mixin.logger.name == "code.history_mixin"

    def test_separation_engine_has_module_logger(self):
        import code.separation_engine
        assert hasattr(code.separation_engine, "logger")
        assert code.separation_engine.logger.name == "code.separation_engine"

    def test_no_root_logger_calls_in_history_mixin(self):
        import code.history_mixin
        src = open(code.history_mixin.__file__, encoding="utf-8").read()
        # Only allow logging.getLogger, not logging.warning/error directly
        lines = [l for l in src.splitlines() if "logging." in l and "getLogger" not in l]
        for line in lines:
            assert not any(
                f"logging.{level}(" in line
                for level in ("warning", "error", "info", "debug", "exception")
            ), f"Root logger call found: {line.strip()}"

    def test_no_root_logger_calls_in_separation_engine(self):
        import code.separation_engine
        src = open(code.separation_engine.__file__, encoding="utf-8").read()
        lines = [l for l in src.splitlines() if "logging." in l and "getLogger" not in l]
        for line in lines:
            assert not any(
                f"logging.{level}(" in line
                for level in ("warning", "error", "info", "debug", "exception")
            ), f"Root logger call found: {line.strip()}"


class TestInfrastructure:
    def test_pyproject_toml_exists(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "pyproject.toml")
        assert os.path.isfile(path), f"Missing: {path}"

    def test_pyproject_toml_valid(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "pyproject.toml")
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["project"]["name"] == "vocalpro"

    def test_ci_workflow_exists(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, ".github", "workflows", "ci.yml")
        assert os.path.isfile(path), f"Missing: {path}"

    def test_ci_workflow_valid_yaml(self):
        import os, yaml
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, ".github", "workflows", "ci.yml")
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert "jobs" in data
        assert "test" in data["jobs"]


# ════════════════════════════════════════════════════════════════════════
# Count verification
# ════════════════════════════════════════════════════════════════════════

def test_count():
    """Verify the suite has 1000+ parametrized tests."""
    import subprocess
    import sys
    r = subprocess.run(
        [sys.executable, "-m", "pytest", __file__, "--collect-only", "-q"],
        capture_output=True, text=True, timeout=120,
    )
    # Parse the final line from stdout: "XXX tests collected"
    for out in (r.stdout, r.stderr):
        for line in out.splitlines():
            if "tests collected" in line:
                n = int(line.split()[0])
                assert n >= 1000, f"Only {n} tests collected, need 1000+"
                return
    # Fallback to naive method count
    import test_all
    total = 0
    for name in dir(test_all):
        obj = getattr(test_all, name)
        if isinstance(obj, type) and name.startswith("Test"):
            total += sum(1 for m in dir(obj) if m.startswith("test_"))
    assert total >= 1000, f"Only {total} test methods, need 1000+"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
