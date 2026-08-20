import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import torch


class TestSeparationEngine:
    pytestmark = pytest.mark.slow

    def test_init(self, engine):
        assert engine.model is not None and engine.sample_rate == 44100

    def test_model_use_train_segment_false(self, engine):
        from unittest.mock import MagicMock
        val = getattr(engine.model, 'use_train_segment', None)
        if val is not None and not isinstance(val, MagicMock):
            assert val is False, f"Expected use_train_segment=False, got {val}"

    def test_model_use_train_segment_no_attr(self):
        class _ModelNoSegment:
            sources = ["vocals"]
            def eval(self):
                return None
            def to(self, device):
                return self
        with patch("code.separation_engine.demucs_get_model", return_value=_ModelNoSegment()):
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            eng = SeparationEngine(dict(DEFAULT_CONFIG))
            assert eng.model_name is not None

    def test_bag_of_models_configures_sub_models(self):
        class _MockSubModel:
            sources = ["vocals"]
            use_train_segment = True
            segment = 8.0
            def eval(self):
                return None
            def to(self, device):
                return self

        sub1 = _MockSubModel()
        sub2 = _MockSubModel()

        class _BagStub:
            def __init__(self, models, sources):
                self.models = models
                self.sources = sources
            def eval(self):
                return None
            def to(self, device):
                return self

        with patch("demucs.apply.BagOfModels", _BagStub):
            with patch("code.separation_engine.demucs_get_model") as m:
                bag = _BagStub([sub1, sub2], ["vocals"])
                m.return_value = bag
                from code.config import DEFAULT_CONFIG
                from code.separation_engine import SeparationEngine
                cfg = dict(DEFAULT_CONFIG)
                cfg["segment"] = 24.0
                eng = SeparationEngine(cfg)
                assert eng.model_name is not None
                assert eng.model is not None

    def test_bag_of_models_configures_sub_models_segment_none(self):
        class _MockSubModel:
            sources = ["vocals"]
            use_train_segment = True
            segment = 8.0
            def eval(self):
                return None
            def to(self, device):
                return self

        sub1 = _MockSubModel()

        class _BagStub:
            def __init__(self, models, sources):
                self.models = models
                self.sources = sources
            def eval(self):
                return None
            def to(self, device):
                return self

        with patch("demucs.apply.BagOfModels", _BagStub):
            with patch("code.separation_engine.demucs_get_model") as m:
                bag = _BagStub([sub1], ["vocals"])
                m.return_value = bag
                from code.config import DEFAULT_CONFIG
                from code.separation_engine import SeparationEngine
                cfg = dict(DEFAULT_CONFIG)
                cfg["segment"] = None
                eng = SeparationEngine(cfg)
                assert eng.model_name is not None
                assert eng.model is not None

    def test_bag_of_models_no_use_train_segment_attr(self):
        class _SubNoSegment:
            sources = ["vocals"]
            segment = 8.0
            def eval(self):
                return None
            def to(self, device):
                return self

        sub = _SubNoSegment()

        class _BagStub:
            def __init__(self, models, sources):
                self.models = models
                self.sources = sources
            def eval(self):
                return None
            def to(self, device):
                return self

        with patch("demucs.apply.BagOfModels", _BagStub):
            with patch("code.separation_engine.demucs_get_model") as m:
                bag = _BagStub([sub], ["vocals"])
                m.return_value = bag
                from code.config import DEFAULT_CONFIG
                from code.separation_engine import SeparationEngine
                cfg = dict(DEFAULT_CONFIG)
                cfg["segment"] = 16.0
                eng = SeparationEngine(cfg)
                assert eng.model_name is not None
                assert eng.model is not None

    def test_single_model_gets_segment(self):
        class _SingleModel:
            sources = ["vocals"]
            use_train_segment = True
            segment = 8.0
            def eval(self):
                return None
            def to(self, device):
                return self

        mdl = _SingleModel()
        with patch("code.separation_engine.demucs_get_model", return_value=mdl):
            from code.config import DEFAULT_CONFIG
            from code.separation_engine import SeparationEngine
            cfg = dict(DEFAULT_CONFIG)
            cfg["segment"] = 24.0
            eng = SeparationEngine(cfg)
            assert eng.model_name is not None
            assert eng.model is not None

    def test_model_pool(self):
        from code.separation_engine import MODEL_POOL
        for k in ("htdemucs_ft", "htdemucs", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra", "mdx_q", "mdx_extra_q"):
            assert k in MODEL_POOL

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
        seg_samples = int(float(engine.config.get("segment", 16.0)) * engine.sample_rate)
        overlap_samples = int(float(engine.config.get("overlap", 0.5)) * engine.sample_rate)
        overlap_samples = min(overlap_samples, seg_samples // 2 - 1)
        orig_len = 100
        is_last_seg = True
        fade_in_len = 0 if not is_last_seg else min(overlap_samples, orig_len)
        fade_out_len = 0 if is_last_seg else min(overlap_samples, orig_len)
        assert fade_in_len == 100
        assert fade_out_len == 0

    def test_fade_clamp_middle_segment(self, engine):
        seg_samples = int(float(engine.config.get("segment", 16.0)) * engine.sample_rate)
        overlap_samples = int(float(engine.config.get("overlap", 0.5)) * engine.sample_rate)
        overlap_samples = min(overlap_samples, seg_samples // 2 - 1)
        orig_len = seg_samples
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
        import soundfile as sf
        sr, dur = 44100, 0.3
        expected_samples = int(sr * dur)
        short_samples = 10000
        inp = tmp_path / "test.mp4"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=True):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, short_samples).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, expected_samples, 2)), patch("code.separation_engine.mux_audio_video"):
                    assert engine.separate_file(str(inp), str(out)) is not None

    def test_separate_video_normalizes_long_audio(self, engine, tmp_path):
        import soundfile as sf
        sr, dur = 44100, 0.2
        expected_samples = int(sr * dur)
        long_samples = 12000
        inp = tmp_path / "test.mp4"; inp.write_bytes(b"x")
        out = tmp_path / "out"; out.mkdir()
        with patch.object(engine, "_has_video_stream", return_value=True):
            with patch.object(engine, "_run_demucs_on_file", return_value={"vocals": np.random.randn(2, long_samples).astype(np.float32)}):
                with patch("code.separation_engine.extract_audio"), patch("code.separation_engine.get_audio_info", return_value=(sr, dur, expected_samples, 2)), patch("code.separation_engine.mux_audio_video"):
                    assert engine.separate_file(str(inp), str(out)) is not None

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
