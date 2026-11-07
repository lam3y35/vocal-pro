"""Golden-output regression & null-test suite for VocalPro v3 DSP stages (N2 quality gate)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "worker"))
sys.path.insert(0, str(ROOT_DIR / "benchmarks"))

from null_test import null_test_and_sdr  # noqa: E402
from vocalpro_worker import dsp  # noqa: E402

GOLDEN_DIR = ROOT_DIR / "benchmarks" / "golden"
REF_DIR = ROOT_DIR / "benchmarks" / "reference-set"


def test_all_dsp_stages_pass_golden_null_test(tmp_path: Path) -> None:
    vocal_bleed, sr = sf.read(str(GOLDEN_DIR / "input_vocal_with_bleed.wav"), dtype="float32")
    vocal_ref, _ = sf.read(str(REF_DIR / "track_01_clean_vocal_ref.wav"), dtype="float32")
    music_ref, _ = sf.read(str(REF_DIR / "track_01_clean_music_ref.wav"), dtype="float32")

    vocal_ch = vocal_bleed.T.copy()
    vocal_ref_ch = vocal_ref.T.copy()
    music_ch = music_ref.T.copy()

    # 1. Vocal Gate
    cand_gate = dsp.apply_vocal_gate(
        vocal_ch.copy(), sr, threshold_db=-55.0, gate_floor_db=-60.0, min_vocal_duration=0.08
    )
    p_gate = tmp_path / "cand_01_gate.wav"
    sf.write(str(p_gate), cand_gate.T, sr, subtype="FLOAT")
    res_gate = null_test_and_sdr(GOLDEN_DIR / "stage_01_vocal_gate.wav", p_gate)
    assert res_gate["passed"], f"Vocal gate null-test failed: {res_gate}"

    # 2. Spectral Denoise (single-band)
    cand_den = dsp.spectral_denoise(vocal_ch.copy(), sr, prop_decrease=0.55)
    p_den = tmp_path / "cand_02_denoise.wav"
    sf.write(str(p_den), cand_den.T, sr, subtype="FLOAT")
    res_den = null_test_and_sdr(GOLDEN_DIR / "stage_02_spectral_denoise_single.wav", p_den)
    assert res_den["passed"], f"Single-band denoise null-test failed: {res_den}"

    # 3. Spectral Denoise (multi-band)
    cand_mb = dsp.spectral_denoise_multiband(
        vocal_ch.copy(),
        sr,
        split_hz=(250.0, 6000.0),
        strength_low=0.35,
        strength_mid=0.10,
        strength_high=0.25,
    )
    p_mb = tmp_path / "cand_03_mb.wav"
    sf.write(str(p_mb), cand_mb.T, sr, subtype="FLOAT")
    res_mb = null_test_and_sdr(GOLDEN_DIR / "stage_03_spectral_denoise_multiband.wav", p_mb)
    assert res_mb["passed"], f"Multi-band denoise null-test failed: {res_mb}"

    # 4. Restore High Frequencies
    cand_hf = dsp.restore_high_frequencies(vocal_ch.copy(), sr, boost_db=3.0, crossover_hz=8000.0)
    p_hf = tmp_path / "cand_04_hf.wav"
    sf.write(str(p_hf), cand_hf.T, sr, subtype="FLOAT")
    res_hf = null_test_and_sdr(GOLDEN_DIR / "stage_04_restore_hf.wav", p_hf)
    assert res_hf["passed"], f"Restore HF null-test failed: {res_hf}"

    # 5. Normalize Loudness
    cand_norm = dsp.normalize_loudness(vocal_ch.copy(), ref_audio=vocal_ref_ch.copy())
    p_norm = tmp_path / "cand_05_norm.wav"
    sf.write(str(p_norm), cand_norm.T, sr, subtype="FLOAT")
    res_norm = null_test_and_sdr(GOLDEN_DIR / "stage_05_normalize_loudness.wav", p_norm)
    assert res_norm["passed"], f"Normalize loudness null-test failed: {res_norm}"

    # 6. Separate SFX (HPSS)
    cand_sfx, cand_harm = dsp.separate_sfx(music_ch.copy(), sr, margin_db=5.0, kernel_size=15)
    p_sfx = tmp_path / "cand_06_sfx.wav"
    p_harm = tmp_path / "cand_06_harm.wav"
    sf.write(str(p_sfx), cand_sfx.T, sr, subtype="FLOAT")
    sf.write(str(p_harm), cand_harm.T, sr, subtype="FLOAT")
    res_sfx = null_test_and_sdr(GOLDEN_DIR / "stage_06_sfx_percussive.wav", p_sfx)
    res_harm = null_test_and_sdr(GOLDEN_DIR / "stage_06_music_harmonic.wav", p_harm)
    assert res_sfx["passed"] and res_harm["passed"], f"HPSS null-test failed: {res_sfx} / {res_harm}"

    # 7. Full postprocess_vocals pipeline
    cand_full = dsp.postprocess_vocals(
        vocal_ch.copy(),
        sr=sr,
        enable_gate=True,
        gate_threshold_db=-55.0,
        gate_floor_db=-60.0,
        enable_denoise=True,
        denoise_prop=0.55,
        min_vocal_duration=0.08,
        trim=False,
        enable_multiband=False,
        denoise_band_split_hz=(250.0, 6000.0),
        denoise_strength_low=0.35,
        denoise_strength_mid=0.10,
        denoise_strength_high=0.25,
        enable_noise_profile=False,
        adaptive_gate=False,
        enable_hf_restore=True,
        hf_boost_db=3.0,
        enable_loudness_normalize=True,
    )
    p_full = tmp_path / "cand_07_full.wav"
    sf.write(str(p_full), cand_full.T, sr, subtype="FLOAT")
    res_full = null_test_and_sdr(GOLDEN_DIR / "stage_07_postprocess_vocals_full.wav", p_full)
    assert res_full["passed"], f"Full postprocess_vocals null-test failed: {res_full}"

    # 8. Smooth crossfade chunks
    half = vocal_ref.shape[0] // 2
    overlap_samples = int(1.0 * sr)
    c1 = vocal_ref[: half + overlap_samples].copy()
    c2 = vocal_ref[half:].copy()
    cand_join = dsp.smooth_crossfade_chunks([c1, c2], overlap_samples=overlap_samples)
    p_join = tmp_path / "cand_08_join.wav"
    sf.write(str(p_join), cand_join, sr, subtype="FLOAT")
    res_join = null_test_and_sdr(GOLDEN_DIR / "stage_08_crossfade_chunks.wav", p_join)
    assert res_join["passed"], f"Crossfade chunks null-test failed: {res_join}"
