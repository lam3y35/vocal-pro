#!/usr/bin/env python3
"""Generate deterministic reference audio/video test fixtures for VocalPro parity & benchmarks."""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

REF_DIR = Path(__file__).resolve().parent / "reference-set"


def synth_vocal_and_music(sr: int, duration_s: float, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (mix_stereo, clean_vocal_stereo, clean_music_stereo) at sample rate sr."""
    rng = np.random.default_rng(seed)
    n = int(sr * duration_s)
    t = np.linspace(0.0, duration_s, n, endpoint=False, dtype=np.float32)

    # Vocal melody: stepped notes (A3=220, C4=261.63, D4=293.66, E4=329.63, G4=392.0) with vibrato & harmonics
    notes = [220.0, 261.63, 293.66, 329.63, 392.0, 329.63, 293.66, 261.63]
    note_len = max(1, n // len(notes))
    f0 = np.zeros(n, dtype=np.float32)
    for i, freq in enumerate(notes):
        start = i * note_len
        end = n if i == len(notes) - 1 else (i + 1) * note_len
        f0[start:end] = freq

    vibrato = 1.0 + 0.008 * np.sin(2.0 * np.pi * 5.5 * t)
    phase = 2.0 * np.pi * np.cumsum(f0 * vibrato) / sr

    vocal_mono = (
        0.45 * np.sin(phase)
        + 0.22 * np.sin(2.0 * phase)
        + 0.12 * np.sin(3.0 * phase)
        + 0.06 * np.sin(4.0 * phase)
        + 0.03 * np.sin(7.0 * phase)  # sibilance/air band > 1.5 kHz
    ).astype(np.float32)

    # Envelope with short breaths between phrases
    phrase_env = (np.sin(np.pi * ((t % 1.5) / 1.5)) ** 0.4).astype(np.float32)
    vocal_mono *= phrase_env * 0.5

    vocal_stereo = np.stack([vocal_mono * 0.98, vocal_mono * 1.02], axis=0)

    # Music bed: bass (110 Hz) + chord pad (440/554/659 Hz) + percussive hi-hat/snare bursts every 0.5s (120 BPM)
    bass = 0.25 * np.sin(2.0 * np.pi * 110.0 * t) + 0.10 * np.sin(2.0 * np.pi * 220.0 * t)
    pad_l = 0.12 * np.sin(2.0 * np.pi * 440.0 * t) + 0.10 * np.sin(2.0 * np.pi * 659.25 * t)
    pad_r = 0.12 * np.sin(2.0 * np.pi * 554.37 * t) + 0.10 * np.sin(2.0 * np.pi * 659.25 * t)

    # 120 BPM percussive clicks/transients (every 0.5s)
    beat_period = int(0.5 * sr)
    drums = np.zeros(n, dtype=np.float32)
    noise = rng.standard_normal(n).astype(np.float32)
    for b in range(0, n, beat_period):
        hit_len = min(int(0.06 * sr), n - b)
        decay = np.exp(-np.linspace(0.0, 8.0, hit_len, dtype=np.float32))
        drums[b : b + hit_len] += 0.35 * noise[b : b + hit_len] * decay

    music_stereo = np.stack([bass + pad_l + drums, bass + pad_r + drums], axis=0).astype(np.float32)
    mix_stereo = np.clip(vocal_stereo + music_stereo, -0.98, 0.98).astype(np.float32)
    return mix_stereo, vocal_stereo, music_stereo


def main() -> None:
    REF_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {}

    # 1. Standard 44.1 kHz stereo track (12s)
    mix_44k, vocal_44k, music_44k = synth_vocal_and_music(44100, 12.0, seed=42)
    p1 = REF_DIR / "track_01_pop_stereo_44k.wav"
    sf.write(str(p1), mix_44k.T, 44100, subtype="PCM_16")
    sf.write(str(REF_DIR / "track_01_clean_vocal_ref.wav"), vocal_44k.T, 44100, subtype="PCM_16")
    sf.write(str(REF_DIR / "track_01_clean_music_ref.wav"), music_44k.T, 44100, subtype="PCM_16")
    manifest["track_01_pop_stereo_44k.wav"] = {"sr": 44100, "channels": 2, "duration_s": 12.0}

    # 2. Mono 48 kHz track (10s)
    mix_48k, _, _ = synth_vocal_and_music(48000, 10.0, seed=7)
    mono_48k = mix_48k.mean(axis=0)
    p2 = REF_DIR / "track_02_mono_48k.wav"
    sf.write(str(p2), mono_48k, 48000, subtype="PCM_16")
    manifest["track_02_mono_48k.wav"] = {"sr": 48000, "channels": 1, "duration_s": 10.0}

    # 3. Very quiet track (-30 dBFS, 8s)
    mix_quiet, _, _ = synth_vocal_and_music(44100, 8.0, seed=99)
    mix_quiet = mix_quiet * (10.0 ** (-30.0 / 20.0))
    p3 = REF_DIR / "track_03_quiet_neg30dbfs.wav"
    sf.write(str(p3), mix_quiet.T, 44100, subtype="PCM_16")
    manifest["track_03_quiet_neg30dbfs.wav"] = {"sr": 44100, "channels": 2, "duration_s": 8.0}

    # 4. Clipped track (0 dBFS, 8s)
    mix_clip, _, _ = synth_vocal_and_music(44100, 8.0, seed=101)
    mix_clip = np.clip(mix_clip * 2.5, -1.0, 1.0)
    p4 = REF_DIR / "track_04_clipped_0dbfs.wav"
    sf.write(str(p4), mix_clip.T, 44100, subtype="PCM_16")
    manifest["track_04_clipped_0dbfs.wav"] = {"sr": 44100, "channels": 2, "duration_s": 8.0}

    # 5. Track with long silence sections (12s: 3s silence, 3s vocal, 3s silence, 3s vocal)
    mix_sil, _, _ = synth_vocal_and_music(44100, 12.0, seed=55)
    mix_sil[:, : 3 * 44100] = 0.0
    mix_sil[:, 6 * 44100 : 9 * 44100] = 0.0
    p5 = REF_DIR / "track_05_silence_sections.wav"
    sf.write(str(p5), mix_sil.T, 44100, subtype="PCM_16")
    manifest["track_05_silence_sections.wav"] = {"sr": 44100, "channels": 2, "duration_s": 12.0}

    # 6. Video file (.mp4 with H.264 video + AAC stereo audio, 8s)
    p6 = REF_DIR / "track_06_video_sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=0x12131a:s=320x240:d=8:r=15",
            "-i",
            str(p1),
            "-t",
            "8",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(p6),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    manifest["track_06_video_sample.mp4"] = {"sr": 44100, "channels": 2, "duration_s": 8.0, "video": True}

    # 7. Corrupt file (truncated WAV header)
    p7 = REF_DIR / "track_07_corrupt.wav"
    p7.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00")
    manifest["track_07_corrupt.wav"] = {"corrupt": True}

    # 8. Zero-length file
    p8 = REF_DIR / "track_08_zero_length.wav"
    p8.write_bytes(b"")
    manifest["track_08_zero_length.wav"] = {"zero_length": True}

    (REF_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Generated reference set:", list(manifest.keys()))


if __name__ == "__main__":
    main()
