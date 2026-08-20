"""Edge/boundary tests for noise-related branches in audio_postprocess.

Covers:
- spectral_denoise with an explicit noise_sample argument
- spectral_denoise_multiband with explicit noise_sample
- compute_adaptive_gate_floor returns configured floor when non-vocal region too short
- separate_sfx accepts asymmetric margin tuple
"""

from __future__ import annotations

import numpy as np
import sys
import types

# Provide a lightweight stub for noisereduce if it's not installed in the test env.
if "noisereduce" not in sys.modules:
    _nr = types.ModuleType("noisereduce")
    def _reduce_noise(y, **kwargs):
        # simple passthrough stub used only for unit tests
        return y
    _nr.reduce_noise = _reduce_noise
    sys.modules["noisereduce"] = _nr


def test_spectral_denoise_with_noise_sample(mono_signal):
    from code.audio_postprocess import spectral_denoise
    a, sr = mono_signal
    # create a short noise sample (quiet noise)
    noise = (np.random.randn(int(0.2 * sr)).astype(np.float32) * 0.01)
    out = spectral_denoise(a, sr=sr, noise_sample=noise)
    assert out.shape == a.shape and np.all(np.isfinite(out))


def test_spectral_denoise_multiband_with_noise_sample(mono_signal):
    from code.audio_postprocess import spectral_denoise_multiband
    a, sr = mono_signal
    noise = (np.random.randn(int(0.5 * sr)).astype(np.float32) * 0.02)
    out = spectral_denoise_multiband(a, sr=sr, noise_sample=noise)
    assert out.shape == a.shape and np.all(np.isfinite(out))


def test_compute_adaptive_gate_floor_short_non_vocal():
    from code.audio_postprocess import compute_adaptive_gate_floor
    sr = 44100
    # create signal where vocal_mask has almost no non-vocal samples
    audio = np.random.randn(int(0.1 * sr)).astype(np.float32) * 0.01
    # mask is ones (all vocal) so non_vocal length is zero (< sr*0.05)
    mask = np.ones(len(audio), dtype=np.float32)
    floor = compute_adaptive_gate_floor(audio, mask, sr=sr, configured_floor_db=-47.0)
    assert floor == -47.0


def test_separate_sfx_with_tuple_margin(mono_signal):
    from code.audio_postprocess import separate_sfx
    a, sr = mono_signal
    # verify function accepts tuple margins and returns two arrays
    h, p = separate_sfx(a, sr=sr, margin_harmonic_db=6.0, margin_percussive_db=1.0, kernel_size=15)
    assert h.shape == a.shape and p.shape == a.shape and np.all(np.isfinite(h)) and np.all(np.isfinite(p))
