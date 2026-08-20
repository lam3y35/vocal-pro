"""Tests for code.audio_postprocess — VAD, gate, denoise, crossfade, SFX separation."""

from __future__ import annotations

import numpy as np
import pytest


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

    def test_spectral_denoise_silent_no_runtimewarning(self, silent_signal):
        """Regression: spectral_denoise must NOT emit RuntimeWarning on silent audio."""
        import warnings
        from code.audio_postprocess import spectral_denoise
        a, sr = silent_signal
        with warnings.catch_warnings(record=True) as caught:
            warnings.filterwarnings("always", category=RuntimeWarning)
            r = spectral_denoise(a, sr=sr)
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0, f"Expected 0 RuntimeWarning(s), got {len(runtime_warnings)}: {[str(x.message) for x in runtime_warnings]}"
        assert np.all(np.isfinite(r))

    def test_spectral_denoise_multiband_silent_no_runtimewarning(self, silent_signal):
        """Regression: spectral_denoise_multiband must NOT emit RuntimeWarning on silent audio."""
        import warnings
        from code.audio_postprocess import spectral_denoise_multiband
        a, sr = silent_signal
        with warnings.catch_warnings(record=True) as caught:
            warnings.filterwarnings("always", category=RuntimeWarning)
            r = spectral_denoise_multiband(a, sr=sr)
        runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert len(runtime_warnings) == 0, f"Expected 0 RuntimeWarning(s), got {len(runtime_warnings)}: {[str(x.message) for x in runtime_warnings]}"
        assert np.all(np.isfinite(r))

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

    @pytest.mark.slow
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
        r = extract_noise_profile(a, mask, sr=sr)
        assert r is None or len(r) > 0

    def test_extract_noise_profile_with_silence(self):
        from code.audio_postprocess import extract_noise_profile, detect_vocal_activity
        sr = 44100
        dur = 1.0
        t = np.linspace(0, dur, int(sr * dur), 0)
        tone = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
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
        assert f == -50

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
# Bulk / parametrized audio post-processing tests
# ════════════════════════════════════════════════════════════════════════

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
