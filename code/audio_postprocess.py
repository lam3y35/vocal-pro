"""Audio post-processing: VAD gating, spectral noise reduction, smooth crossfade.

Three techniques that run after HTDemucs separation to produce cleaner output:
1. Vocal Activity Detection + gating — silence instrumental-only sections
2. Spectral noise reduction — remove residual music bleed from vocal segments
3. Smooth crossfade — seamless chunk merging with equal-power curves

Improvements:
- Multi-band denoising: each frequency band gets its own denoising strength
- Noise-profile extraction: VAD-identified silence used as noise reference
- Adaptive gate floor: adjusts based on actual noise floor
"""

import gc
import logging
from typing import Optional

import librosa
import noisereduce as nr
import numpy as np
from scipy.ndimage import maximum_filter, median_filter, uniform_filter1d
from scipy.signal import butter, sosfiltfilt

logger = logging.getLogger(__name__)

# ── Vocal Activity Detection + Gating ───────────────────────────────────


def detect_vocal_activity(
    audio: np.ndarray,
    sr: int = 44100,
    frame_length: int = 2048,
    hop_length: int = 512,
    threshold_db: float = -40.0,
    min_vocal_duration: float = 0.1,
    margin_frames: int = 4,
) -> np.ndarray:
    """Return a smooth gain envelope (0..1) marking where vocals are present.

    Uses RMS energy in the vocal frequency range (200 Hz–5 kHz) combined with
    a spectral flatness metric to distinguish vocals from music/noise.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        frame_length: STFT window size.
        hop_length: STFT hop size.
        threshold_db: RMS threshold in dB below peak for vocal detection.
        min_vocal_duration: Minimum vocal segment duration in seconds.
        margin_frames: Extra frames of context around detected vocal segments.
    """
    # Mix to mono if stereo
    if audio.ndim == 2:
        mono = audio.mean(axis=0)
    else:
        mono = audio

    total_samples = len(mono)

    # ── RMS energy ──
    rms = librosa.feature.rms(y=mono, frame_length=frame_length, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max)

    # ── Spectral flatness (lower = more tonal/vocal-like) ──
    flatness = librosa.feature.spectral_flatness(y=mono, hop_length=hop_length)[0]

    # ── Spectral centroid in vocal range ──
    S = np.abs(librosa.stft(mono, n_fft=frame_length, hop_length=hop_length))
    centroid = librosa.feature.spectral_centroid(S=S, sr=sr, hop_length=hop_length)[0]
    centroid_norm = np.clip((centroid - 500) / 3000, 0, 1)

    # ── Combine features for vocal probability ──
    vocal_score = (
        (rms_db > threshold_db).astype(np.float32) * 0.5
        + (1.0 - flatness) * 0.3
        + centroid_norm * 0.2
    )

    # ── Convert to sample-level mask ──
    n_frames = len(vocal_score)
    # Vectorized expansion: repeat each frame value across frame_length samples
    mask = np.repeat(vocal_score, hop_length).astype(np.float32)
    # Trim or pad to exact total_samples length
    if len(mask) > total_samples:
        mask = mask[:total_samples]
    elif len(mask) < total_samples:
        mask = np.pad(mask, (0, total_samples - len(mask)))

    # ── Smooth the mask ──
    kernel_size = max(3, int(min_vocal_duration * sr / hop_length))
    if kernel_size % 2 == 0:
        kernel_size += 1
    mask = median_filter(mask, size=kernel_size)

    # ── Expand vocal segments by margin_frames ──
    margin_samples = margin_frames * hop_length
    if margin_samples > 1:
        mask = maximum_filter(mask, size=margin_samples)

    # ── Smooth transitions with a raised-cosine ramp ──
    fade_len = int(0.02 * sr)
    if fade_len > 0:
        diff = np.diff(mask, prepend=0, append=0)
        rise_starts = np.where(diff > 0.5)[0]
        fall_ends = np.where(diff < -0.5)[0]

        for idx in rise_starts:
            ramp_end = min(idx + fade_len, total_samples)
            ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, ramp_end - idx)))
            mask[idx:ramp_end] = np.minimum(mask[idx:ramp_end], ramp)

        for idx in fall_ends:
            ramp_start = max(idx - fade_len, 0)
            ramp = 0.5 * (1 + np.cos(np.linspace(0, np.pi, idx - ramp_start)))
            mask[ramp_start:idx] = np.minimum(mask[ramp_start:idx], ramp)

    return np.clip(mask, 0.0, 1.0)


def apply_vocal_gate(
    audio: np.ndarray,
    sr: int = 44100,
    threshold_db: float = -40.0,
    gate_floor_db: float = -60.0,
    attack_ms: float = 10.0,
    release_ms: float = 100.0,
    min_vocal_duration: float = 0.1,
    vocal_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Gate vocal audio: preserve vocal segments, silence instrumental-only parts.

    Args:
        audio: (channels, samples) float32 array.
        sr: Sample rate.
        threshold_db: RMS threshold for vocal detection.
        gate_floor_db: Floor level for gated (silent) sections in dB.
        attack_ms: Attack time in milliseconds.
        release_ms: Release time in milliseconds.
        min_vocal_duration: Minimum vocal segment duration to keep.
        vocal_mask: Optional pre-computed mask from detect_vocal_activity.
            If provided, skips internal VAD computation.

    Returns:
        Gated audio with same shape as input.
    """
    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[np.newaxis, :]

    channels, total_samples = audio.shape

    if vocal_mask is not None:
        mask = vocal_mask
    else:
        mono = audio.mean(axis=0)
        mask = detect_vocal_activity(
            mono, sr=sr,
            threshold_db=threshold_db,
            min_vocal_duration=min_vocal_duration,
        )

    floor = 10 ** (gate_floor_db / 20.0)
    gain = floor + (1.0 - floor) * mask

    attack_samples = int(attack_ms * sr / 1000)
    release_samples = int(release_ms * sr / 1000)

    if attack_samples > 1 or release_samples > 1:
        kernel = max(3, max(attack_samples, release_samples))
        gain = uniform_filter1d(gain, size=kernel)

    gated = audio * gain[np.newaxis, :]
    if was_1d:
        gated = gated.squeeze(0)
    return gated


# ── Noise Profile Extraction ───────────────────────────────────────────


def extract_noise_profile(
    audio: np.ndarray,
    vocal_mask: np.ndarray,
    sr: int = 44100,
    min_duration: float = 0.5,
) -> Optional[np.ndarray]:
    """Extract a noise sample from the quietest non-vocal region.

    Uses the VAD mask to find silent sections, then picks the quietest
    500ms segment for use as a noise profile in spectral denoising.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        vocal_mask: (samples,) float32 array with 1 = vocal, 0 = non-vocal.
        sr: Sample rate.
        min_duration: Minimum duration of noise sample in seconds.

    Returns:
        Mono noise sample as (samples,) float32, or None if no suitable
        non-vocal region found.
    """
    min_samples = int(min_duration * sr)
    if audio.ndim == 2:
        mono = audio.mean(axis=0)
    else:
        mono = audio

    silent = (vocal_mask < 0.01).astype(np.int32)
    diff = np.diff(silent, prepend=0, append=0)
    starts = np.where(diff == 1)[0]
    ends = np.where(diff == -1)[0]

    if len(starts) == 0:
        return None

    # Score each silent region by RMS energy, pick the quietest one
    best_score = np.inf
    best_region = None
    for s, e in zip(starts, ends):
        if e - s < min_samples:
            continue
        region = mono[s:e]
        rms = np.sqrt(np.mean(region ** 2))
        if rms < best_score:
            best_score = rms
            best_region = (s, e)

    if best_region is None:
        return None

    s, e = best_region
    mid = (s + e) // 2
    half = min_samples // 2
    seg_start = max(0, mid - half)
    seg_end = min(len(mono), mid + half)
    return mono[seg_start:seg_end].copy()


# ── Adaptive Gate Floor ────────────────────────────────────────────────


def compute_adaptive_gate_floor(
    audio: np.ndarray,
    vocal_mask: np.ndarray,
    sr: int = 44100,
    configured_floor_db: float = -50.0,
    headroom_db: float = 3.0,
) -> float:
    """Compute an adaptive gate floor from the noise floor of non-vocal sections.

    Ensures the gate floor is no lower than configured_floor_db, but also
    not higher than the actual noise floor + headroom.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        vocal_mask: (samples,) float32 array with vocal activity (0..1).
        sr: Sample rate.
        configured_floor_db: User-configured minimum gate floor in dB.
        headroom_db: Headroom above measured noise floor in dB.

    Returns:
        Gate floor in dB.
    """
    if audio.ndim == 2:
        mono = audio.mean(axis=0)
    else:
        mono = audio

    non_vocal = mono[vocal_mask < 0.01]
    if len(non_vocal) < int(sr * 0.05):
        return configured_floor_db

    rms = np.sqrt(np.mean(non_vocal ** 2))
    rms_db = 20 * np.log10(max(rms, 1e-12))
    adaptive = rms_db + headroom_db
    return max(adaptive, configured_floor_db)


# ── Spectral Noise Reduction (Single-band) ─────────────────────────────


def spectral_denoise(
    audio: np.ndarray,
    sr: int = 44100,
    reduction_db: float = 12.0,
    prop_decrease: float = 0.85,
    n_fft: int = 2048,
    noise_sample: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Reduce residual music bleed using spectral gating noise reduction.

    Uses the noisereduce library with non-stationary mode to adapt to
    varying music backgrounds across the track.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        reduction_db: Noise reduction strength in dB.
        prop_decrease: Proportion of noise to remove (0.0–1.0).
        n_fft: FFT size for spectral analysis.
        noise_sample: Optional noise profile. If provided, used as the noise
            reference instead of estimating from the signal itself.

    Returns:
        Denoised audio with same shape as input.
    """
    orig_shape = audio.shape

    if audio.size == 0:
        return audio.copy()

    max_val = np.max(np.abs(audio))
    if max_val < 1e-12:
        return audio.copy()

    kwargs = dict(
        sr=sr,
        stationary=False,
        prop_decrease=prop_decrease,
        n_fft=n_fft,
        freq_mask_smooth_hz=500,
        time_mask_smooth_ms=50,
    )
    if noise_sample is not None:
        kwargs["y_noise"] = noise_sample

    if audio.ndim == 1:
        denoised = nr.reduce_noise(y=audio, **kwargs)
    else:
        # noisereduce supports stereo natively — pass the full array
        denoised = nr.reduce_noise(y=audio, **kwargs)

    if not np.all(np.isfinite(denoised)):
        denoised = np.nan_to_num(denoised, copy=False)

    return denoised.reshape(orig_shape)


# ── SFX Separation from Music (HPSS) ──────────────────────────────────


def separate_sfx(
    audio: np.ndarray,
    sr: int = 44100,
    margin_db: float = 5.0,
    kernel_size: int = 31,
) -> tuple[np.ndarray, np.ndarray]:
    """Separate a mixed audio signal into music (harmonic) and SFX (percussive).

    Uses HPSS (Harmonic-Percussive Source Separation) via librosa to decompose
    the signal. The harmonic component contains sustained musical tones, while
    the percussive component contains transients, impacts, sound effects, etc.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        margin_db: Separation margin in dB (higher = more aggressive separation).
        kernel_size: Median filter kernel size for HPSS (odd).

    Returns:
        (harmonic, percussive) tuple, each with same shape as input.
    """
    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[np.newaxis, :]

    channels = audio.shape[0]
    harmonic = np.zeros_like(audio)
    percussive = np.zeros_like(audio)

    for ch in range(channels):
        h, p = librosa.effects.hpss(
            audio[ch],
            kernel_size=kernel_size,
            margin=margin_db,
        )
        harmonic[ch] = h
        percussive[ch] = p

    if was_1d:
        harmonic = harmonic.squeeze(0)
        percussive = percussive.squeeze(0)

    return harmonic, percussive


# ── Multi-band Spectral Noise Reduction ────────────────────────────────


def _sos_filter(sr: int, cutoff_hz: float, btype: str, order: int = 4):
    return butter(order, cutoff_hz, btype=btype, fs=sr, output="sos")


def spectral_denoise_multiband(
    audio: np.ndarray,
    sr: int = 44100,
    split_hz: tuple[float, float] = (250.0, 6000.0),
    strength_low: float = 0.90,
    strength_mid: float = 0.65,
    strength_high: float = 0.80,
    noise_sample: Optional[np.ndarray] = None,
    n_fft: int = 2048,
) -> np.ndarray:
    """Multi-band spectral denoising with per-band strength.

    Splits the signal into low/mid/high bands and applies different denoising
    strengths to each. The mid band (vocal range) gets the gentlest treatment,
    low band (rumble) and high band (hiss) get heavier treatment.

    Band reconstruction is exact: low + mid + high = original signal, so no
    energy is lost or doubled at crossover frequencies.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        split_hz: (low_cut, high_cut) — frequencies that split the bands.
        strength_low: Denoise strength for low band (0..1).
        strength_mid: Denoise strength for mid band (0..1).
        strength_high: Denoise strength for high band (0..1).
        noise_sample: Optional noise profile for reference.
        n_fft: FFT size.

    Returns:
        Denoised audio with same shape as input.
    """
    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[np.newaxis, :]

    channels = audio.shape[0]
    low_cut, high_cut = split_hz

    sos_low = _sos_filter(sr, low_cut, "low", order=4)
    sos_high = _sos_filter(sr, high_cut, "high", order=4)

    kwargs = dict(
        sr=sr,
        stationary=False,
        n_fft=n_fft,
        freq_mask_smooth_hz=500,
        time_mask_smooth_ms=50,
    )
    if noise_sample is not None:
        kwargs["y_noise"] = noise_sample

    denoised = np.zeros_like(audio)

    for ch in range(channels):
        signal = audio[ch]

        # Split into bands using zero-phase Butterworth filters.
        # low + mid + high = original signal exactly.
        low = sosfiltfilt(sos_low, signal)
        high = sosfiltfilt(sos_high, signal)
        mid = signal - low - high

        low_d = nr.reduce_noise(y=low, prop_decrease=strength_low, **kwargs)
        mid_d = nr.reduce_noise(y=mid, prop_decrease=strength_mid, **kwargs)
        high_d = nr.reduce_noise(y=high, prop_decrease=strength_high, **kwargs)

        denoised[ch] = low_d + mid_d + high_d

    if was_1d:
        denoised = denoised.squeeze(0)

    if not np.all(np.isfinite(denoised)):
        denoised = np.nan_to_num(denoised, copy=False)

    return denoised


# ── Silence Trimming ────────────────────────────────────────────────────


def trim_silence(
    audio: np.ndarray,
    sr: int = 44100,
    top_db: float = 40.0,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    """Trim leading and trailing silence from an audio signal.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        top_db: The threshold (in dB) below reference to consider as silence.
    """
    if audio.ndim == 2:
        mono = audio.mean(axis=0)
    else:
        mono = audio

    trimmed_mono, index = librosa.effects.trim(
        mono, top_db=top_db, frame_length=frame_length, hop_length=hop_length
    )

    start, end = index
    if audio.ndim == 2:
        return audio[:, start:end]
    else:
        return audio[start:end]


# ── Smooth Crossfade (Overlap-Add) ──────────────────────────────────────


def smooth_crossfade_chunks(
    chunk_arrays: list[np.ndarray],
    overlap_samples: int,
    sr: int = 44100,
    fade_curve: str = "equal_power",
) -> np.ndarray:
    """Merge overlapping audio chunks with smooth equal-power crossfade.

    This replaces the ffmpeg acrossfade approach with a proper OLA (overlap-add)
    implementation that produces seamless transitions.

    Args:
        chunk_arrays: List of (samples, channels) or (samples,) float32 arrays.
        overlap_samples: Number of samples to overlap between adjacent chunks.
        sr: Sample rate (for fade length calculation).
        fade_curve: "equal_power" (raised cosine) or "linear".

    Returns:
        Merged audio array (samples, channels).
    """
    if not chunk_arrays:
        raise ValueError("No chunks to merge")
    if len(chunk_arrays) == 1:
        chunk = chunk_arrays[0]
        return chunk[:, np.newaxis] if chunk.ndim == 1 else chunk

    chunks = []
    for c in chunk_arrays:
        if c.ndim == 1:
            c = c[:, np.newaxis]
        chunks.append(c)

    n = len(chunks)
    n_channels = chunks[0].shape[1]
    nominal_len = chunks[0].shape[0]
    overlap = max(0, int(overlap_samples))
    hop = nominal_len - overlap
    if hop <= 0:
        hop = max(1, nominal_len // 2)
        overlap = nominal_len - hop

    total_len = max(i * hop + chunk.shape[0] for i, chunk in enumerate(chunks))

    output = np.zeros((total_len, n_channels), dtype=np.float32)
    weight_sum = np.zeros((total_len, 1), dtype=np.float32)

    for i, chunk in enumerate(chunks):
        chunk_len = chunk.shape[0]
        start = i * hop
        w = np.ones(chunk_len, dtype=np.float32)

        v = min(overlap, chunk_len)
        if v > 0:
            k = np.arange(v, dtype=np.float32)
            if fade_curve == "linear":
                rise = k / v
            else:
                rise = 0.5 * (1.0 - np.cos(np.pi * k / v))
            if i > 0:
                w[:v] = rise
            if i < n - 1:
                w[chunk_len - v:] = rise[::-1]

        end = start + chunk_len
        output[start:end] += chunk * w[:, np.newaxis]
        weight_sum[start:end] += w[:, np.newaxis]

    np.divide(output, np.maximum(weight_sum, 1e-8), out=output)
    return output


# ── Combined Post-Processing Pipeline ───────────────────────────────────


def postprocess_vocals(
    vocals: np.ndarray,
    sr: int = 44100,
    enable_gate: bool = True,
    gate_threshold_db: float = -40.0,
    gate_floor_db: float = -60.0,
    enable_denoise: bool = True,
    denoise_prop: float = 0.85,
    min_vocal_duration: float = 0.1,
    trim: bool = False,
    enable_multiband: bool = True,
    denoise_band_split_hz: tuple[float, float] = (250.0, 6000.0),
    denoise_strength_low: float = 0.90,
    denoise_strength_mid: float = 0.65,
    denoise_strength_high: float = 0.80,
    enable_noise_profile: bool = True,
    adaptive_gate: bool = True,
) -> np.ndarray:
    """Full post-processing pipeline for separated vocals.

    1. Extract noise profile from VAD-identified silent sections (if enabled)
    2. Apply vocal gate to silence instrumental-only sections
    3. Apply spectral denoise (single-band or multi-band) to reduce residual bleed
    4. Trim leading/trailing silence

    Args:
        vocals: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        enable_gate: Whether to apply vocal activity gating.
        gate_threshold_db: Threshold for vocal detection.
        gate_floor_db: Floor level for gated sections.
        enable_denoise: Whether to apply spectral noise reduction.
        denoise_prop: Proportion of noise to remove (single-band mode).
        min_vocal_duration: Minimum vocal segment duration to keep.
        trim: Whether to trim leading/trailing silence.
        enable_multiband: Use multi-band denoising instead of single-band.
        denoise_band_split_hz: (low_cut, high_cut) for multi-band splitting.
        denoise_strength_low: Denoise strength for low band.
        denoise_strength_mid: Denoise strength for mid band.
        denoise_strength_high: Denoise strength for high band.
        enable_noise_profile: Extract noise profile from VAD silence.
        adaptive_gate: Compute gate floor adaptively from noise floor.

    Returns:
        Processed vocals with same shape as input (unless trimmed).
    """
    result = vocals.copy()
    vocal_mask = None
    noise_sample = None

    # ── Step 0: Compute VAD mask once, reuse for profiling + gating ──
    if enable_gate or (enable_denoise and enable_noise_profile):
        if result.ndim == 2:
            mono = result.mean(axis=0)
        else:
            mono = result
        vocal_mask = detect_vocal_activity(
            mono, sr=sr,
            threshold_db=gate_threshold_db,
            min_vocal_duration=min_vocal_duration,
        )

    # ── Step 1: Extract noise profile from non-vocal sections ──
    if enable_denoise and enable_noise_profile and vocal_mask is not None:
        noise_sample = extract_noise_profile(result, vocal_mask, sr=sr)
        if noise_sample is not None:
            logger.info("Extracted noise profile (%.2f samples)", len(noise_sample))

    # ── Step 2: Apply vocal gate ──
    if enable_gate:
        floor_db = gate_floor_db
        if adaptive_gate and vocal_mask is not None:
            floor_db = compute_adaptive_gate_floor(
                result, vocal_mask, sr=sr,
                configured_floor_db=gate_floor_db,
            )
            if floor_db != gate_floor_db:
                logger.info("Adaptive gate floor: %.1f dB (configured: %.1f dB)",
                            floor_db, gate_floor_db)
        logger.info("Applying vocal activity gate (threshold=%s dB, floor=%s dB)",
                    gate_threshold_db, floor_db)
        result = apply_vocal_gate(
            result, sr=sr,
            threshold_db=gate_threshold_db,
            gate_floor_db=floor_db,
            min_vocal_duration=min_vocal_duration,
            vocal_mask=vocal_mask,
        )

    # ── Step 3: Apply spectral denoise ──
    if enable_denoise:
        if enable_multiband:
            logger.info(
                "Applying multi-band denoising (low=%.2f, mid=%.2f, high=%.2f)",
                denoise_strength_low, denoise_strength_mid, denoise_strength_high,
            )
            result = spectral_denoise_multiband(
                result, sr=sr,
                split_hz=denoise_band_split_hz,
                strength_low=denoise_strength_low,
                strength_mid=denoise_strength_mid,
                strength_high=denoise_strength_high,
                noise_sample=noise_sample,
            )
        else:
            logger.info("Applying spectral noise reduction (prop=%.2f)", denoise_prop)
            result = spectral_denoise(
                result, sr=sr,
                prop_decrease=denoise_prop,
                noise_sample=noise_sample,
            )

    # ── Step 4: Trim silence ──
    if trim:
        logger.info("Trimming silence")
        result = trim_silence(result, sr=sr)

    return result
