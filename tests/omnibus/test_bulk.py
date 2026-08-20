import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


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
    @pytest.mark.slow
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
    pytestmark = pytest.mark.slow
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
            eng = SeparationEngine(dict(DEFAULT_CONFIG))
            eng.update_config({cfg_key: cfg_val})
            assert eng.config[cfg_key] == cfg_val
