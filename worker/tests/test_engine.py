"""Integration tests for VocalPro v3 Separation Engine, Analysis, MIDI, and Bug Fixes (P-05, P-07, P-08, P-17, P-18)."""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "worker"))

from vocalpro_worker.analysis import analyze_audio_file  # noqa: E402
from vocalpro_worker.engine import WorkerEngineError, run_separation_job  # noqa: E402
from vocalpro_worker.midi import stem_to_midi_file  # noqa: E402

REF_DIR = ROOT_DIR / "benchmarks" / "reference-set"


@pytest.fixture(autouse=True)
def fast_model_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOCALPRO_TEST_FAST_MODEL", "1")


def test_htdemucs_6s_writes_all_six_stems_fixing_p07(tmp_path: Path) -> None:
    """SEP-03 & SEP-09 (Bug P-07 fix): htdemucs_6s writes all 6 stems to disk."""
    events: list[dict] = []
    res = run_separation_job(
        job_id="j-6s",
        input_path_str=str(REF_DIR / "track_01_pop_stereo_44k.wav"),
        output_dir_str=str(tmp_path / "out_6s"),
        options={
            "model": "htdemucs_6s",
            "output_mode": "all_stems",
            "output_format": "wav",
            "audio_bitrate": "320k",
            "output_all_stems": True,
            "device": "cpu",
            "shifts": 0,
            "overlap": 0.25,
            "segment": 4.0,
            "enable_vocal_gate": False,
            "enable_spectral_denoise": False,
        },
        cancel_event=threading.Event(),
        emit_event=events.append,
    )
    stem_names = {s["name"] for s in res["stems"]}
    assert {"vocals", "drums", "bass", "other", "guitar", "piano"}.issubset(stem_names)
    for stem in res["stems"]:
        assert Path(stem["path"]).is_file()
        assert Path(stem["path"]).stat().st_size > 1000
    assert any(e["event"] == "progress" and e["phase"] == "inference" for e in events)


def test_large_file_chunked_path_and_sfx_mp3_encoding_fixes_p08_and_p17(tmp_path: Path) -> None:
    """SEP-05 + Bug P-08 + Bug P-17 + Bug P-18: chunked separation + SFX mix + MP3 encode."""
    res = run_separation_job(
        job_id="j-chunk-mp3",
        input_path_str=str(REF_DIR / "track_01_pop_stereo_44k.wav"),
        output_dir_str=str(tmp_path / "out_chunk"),
        options={
            "model": "htdemucs",
            "output_mode": "vocals",
            "output_format": "mp3",
            "audio_bitrate": "192k",
            "device": "cpu",
            "shifts": 0,
            "overlap": 0.25,
            "segment": 4.0,
            # Force large-file chunked path on 12s audio (threshold = 0.1 min = 6s, chunk = 0.1 min = 6s)
            "large_file_threshold_minutes": 0.1,
            "chunk_duration_minutes": 0.1,
            "overlap_seconds": 1.0,
            "enable_sfx_separation": True,
            "include_sfx": True,
            "save_background_track": True,
            "karaoke_mode": True,
            "generate_comparison_samples": True,
            "enable_vocal_gate": True,
            "enable_spectral_denoise": True,
        },
        cancel_event=threading.Event(),
        emit_event=lambda _: None,
    )
    stem_map = {s["name"]: Path(s["path"]) for s in res["stems"]}
    assert "vocals" in stem_map and stem_map["vocals"].suffix == ".mp3"
    assert stem_map["vocals"].is_file() and stem_map["vocals"].stat().st_size > 1000
    assert "karaoke" in stem_map and stem_map["karaoke"].is_file()
    assert "background" in stem_map and stem_map["background"].is_file()
    assert len(res["comparison_samples"]) >= 2


def test_video_input_extraction_and_remux_in02(tmp_path: Path) -> None:
    """IN-02: MP4 video input extracts audio, separates vocals, and muxes {base_name}_clean.mp4."""
    res = run_separation_job(
        job_id="j-vid",
        input_path_str=str(REF_DIR / "track_06_video_sample.mp4"),
        output_dir_str=str(tmp_path / "out_vid"),
        options={
            "model": "htdemucs",
            "output_mode": "vocals",
            "output_format": "wav",
            "audio_bitrate": "192k",
            "device": "cpu",
            "shifts": 0,
            "overlap": 0.25,
            "segment": 4.0,
            "output_video": True,
            "video_output_mode": "both",
            "enable_vocal_gate": False,
            "enable_spectral_denoise": False,
        },
        cancel_event=threading.Event(),
        emit_event=lambda _: None,
    )
    stem_map = {s["name"]: Path(s["path"]) for s in res["stems"]}
    assert "vocals" in stem_map and stem_map["vocals"].is_file()
    assert "video_clean" in stem_map and stem_map["video_clean"].name == "track_06_video_sample_clean.mp4"
    assert stem_map["video_clean"].stat().st_size > 1000


def test_analyze_audio_and_stem_to_midi(tmp_path: Path) -> None:
    """ANA-01 & ANA-02: BPM, Key, 8000-point waveform, and Stem-to-MIDI."""
    ana = analyze_audio_file(REF_DIR / "track_01_pop_stereo_44k.wav")
    assert ana["bpm"] == 117.0
    assert ana["key"] == "A Minor"
    assert len(ana["waveform"]) == 8000

    out_mid = tmp_path / "vocal.mid"
    notes = stem_to_midi_file(REF_DIR / "track_01_clean_vocal_ref.wav", out_mid)
    assert notes == 8
    assert out_mid.is_file() and out_mid.read_bytes().startswith(b"MThd")


def test_corrupt_and_zero_length_inputs_raise_structured_error(tmp_path: Path) -> None:
    """Negative tests: corrupt and 0-byte files raise DECODE_FAILED without crashing worker."""
    with pytest.raises(WorkerEngineError) as exc_zero:
        run_separation_job(
            job_id="j-zero",
            input_path_str=str(REF_DIR / "track_08_zero_length.wav"),
            output_dir_str=str(tmp_path),
            options={"model": "htdemucs", "output_mode": "vocals", "output_format": "wav", "device": "cpu"},
            cancel_event=threading.Event(),
            emit_event=lambda _: None,
        )
    assert exc_zero.value.code == "DECODE_FAILED"

    with pytest.raises(WorkerEngineError) as exc_corrupt:
        run_separation_job(
            job_id="j-corrupt",
            input_path_str=str(REF_DIR / "track_07_corrupt.wav"),
            output_dir_str=str(tmp_path),
            options={"model": "htdemucs", "output_mode": "vocals", "output_format": "wav", "device": "cpu"},
            cancel_event=threading.Event(),
            emit_event=lambda _: None,
        )
    assert exc_corrupt.value.code == "DECODE_FAILED"


def test_hardware_profile_detection_and_parallel_dsp_bit_exactness(tmp_path: Path) -> None:
    """Verify hardware profile detection and that parallel 6-band DSP is 100% bit-identical to sequential DSP."""
    import numpy as np
    import soundfile as sf
    from vocalpro_worker.dsp import separate_sfx, spectral_denoise_multiband
    from vocalpro_worker.hardware import detect_hardware_profile

    hw = detect_hardware_profile(tmp_path)
    assert hw.logical_cores >= 1
    assert hw.total_ram_mb > 0
    assert hw.device_tier in {
        "ultra_gpu",
        "high_gpu",
        "entry_gpu",
        "workstation_cpu",
        "standard_cpu",
        "low_resource",
    }
    assert hw.recommended_max_concurrent_jobs >= 1

    audio_2d, sr = sf.read(str(REF_DIR / "track_01_pop_stereo_44k.wav"), dtype="float32", always_2d=True)
    audio_ch = audio_2d.T[:, : sr * 3]  # 3s stereo slice

    seq_out = spectral_denoise_multiband(audio_ch, sr=sr, parallel=False)
    par_out = spectral_denoise_multiband(audio_ch, sr=sr, parallel=True)
    assert float(np.max(np.abs(seq_out - par_out))) == 0.0

    h_seq, p_seq = separate_sfx(audio_ch, sr=sr, parallel=False)
    h_par, p_par = separate_sfx(audio_ch, sr=sr, parallel=True)
    assert float(np.max(np.abs(h_seq - h_par))) == 0.0
    assert float(np.max(np.abs(p_seq - p_par))) == 0.0

