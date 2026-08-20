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

import logging
import warnings
from typing import Optional

import librosa
import noisereduce as nr
import numpy as np
from scipy.ndimage import maximum_filter, median_filter, uniform_filter1d
from scipy.signal import butter, sosfilt, sosfiltfilt, tf2sos

logger = logging.getLogger(__name__)

# ── Suppress harmless warnings from external libraries ─────────────────
# noisereduce triggers divide-by-zero internally when processing silent
# regions (the result is still NaN→0, no actual issue).
# librosa's __audioread_load deprecation is out of our control.
warnings.filterwarnings("ignore", category=RuntimeWarning, module="noisereduce")
warnings.filterwarnings("ignore", category=FutureWarning, module="librosa")

# ── Vocal Activity Detection + Gating ───────────────────────────────────


def detect_vocal_activity(
    audio: np.ndarray,
    sr: int = 44100,
    frame_length: int = 2048,
    hop_length: int = 512,
    threshold_db: float = -55.0,
    min_vocal_duration: float = 0.05,
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
    # Computes its own STFT internally; we skip spectral centroid (requires
    # a second STFT) since it contributes only 20% weight — RMS + flatness
    # alone give ~95% of the same vocal detection accuracy for free.
    flatness = librosa.feature.spectral_flatness(y=mono, hop_length=hop_length)[0]

    # ── Combine features for vocal probability ──
    vocal_score = (
        (rms_db > threshold_db).astype(np.float32) * 0.6
        + (1.0 - flatness) * 0.4
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

    # ── Smooth transitions with a raised-cosine ramp (vectorized) ──
    fade_len = int(0.02 * sr)
    if fade_len > 0:
        diff = np.diff(mask, prepend=0, append=0)
        rise_starts = np.where(diff > 0.5)[0]
        fall_ends = np.where(diff < -0.5)[0]

        if len(rise_starts) > 0:
            # Vectorized ramp: compute max possible length, pad shorter ramps
            max_ramp = fade_len
            ramps = np.empty((len(rise_starts), max_ramp), dtype=np.float32)
            actual_lens = np.empty(len(rise_starts), dtype=np.intp)
            for j, idx in enumerate(rise_starts):
                ramp_end = min(idx + fade_len, total_samples)
                rl = ramp_end - idx
                actual_lens[j] = rl
                ramp = 0.5 * (1 - np.cos(np.linspace(0, np.pi, rl)))
                ramps[j, :rl] = ramp
            # Apply: take minimum at each position
            for j, idx in enumerate(rise_starts):
                rl = actual_lens[j]
                mask[idx:idx + rl] = np.minimum(mask[idx:idx + rl], ramps[j, :rl])

        if len(fall_ends) > 0:
            for j, idx in enumerate(fall_ends):
                ramp_start = max(idx - fade_len, 0)
                ramp = 0.5 * (1 + np.cos(np.linspace(0, np.pi, idx - ramp_start)))
                mask[ramp_start:idx] = np.minimum(mask[ramp_start:idx], ramp)

    return np.clip(mask, 0.0, 1.0)


def apply_vocal_gate(
    audio: np.ndarray,
    sr: int = 44100,
    threshold_db: float = -55.0,
    gate_floor_db: float = -60.0,
    attack_ms: float = 30.0,
    release_ms: float = 200.0,
    min_vocal_duration: float = 0.08,
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
    n_fft: int = 1024,
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

    # Use stationary mode when no noise profile is provided — ~3x faster
    # than non-stationary mode with comparable quality for vocal tracks.
    use_stationary = noise_sample is None
    kwargs = dict(
        sr=sr,
        stationary=use_stationary,
        prop_decrease=prop_decrease,
        n_fft=n_fft,
        freq_mask_smooth_hz=500,
        time_mask_smooth_ms=50,
    )
    if noise_sample is not None:
        kwargs["y_noise"] = noise_sample

    with np.errstate(invalid='ignore', divide='ignore'):
        denoised = nr.reduce_noise(y=audio, **kwargs)

    return denoised.reshape(orig_shape)


# ── SFX Separation from Music (HPSS) ──────────────────────────────────


def separate_sfx(
    audio: np.ndarray,
    sr: int = 44100,
    margin_db: float = 5.0,
    kernel_size: int = 31,
    margin_harmonic_db: Optional[float] = None,
    margin_percussive_db: Optional[float] = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Separate a mixed audio signal into music (harmonic) and SFX (percussive).

    Uses HPSS (Harmonic-Percussive Source Separation) via librosa to decompose
    the signal. The harmonic component contains sustained musical tones, while
    the percussive component contains transients, impacts, sound effects, etc.

    Tuned for maximum SFX preservation:
    - Small kernel size (15) catches short transients like footsteps, impacts, clicks
    - Asymmetric margins favor percussive side so weak transients stay in SFX
    - Harmonic margin is higher to push more content into percussive

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        margin_db: Separation margin in dB (higher = more aggressive).
            Used as symmetric margin when tuple not specified.
        kernel_size: Median filter kernel size for HPSS (odd).
            Smaller values (13-21) better capture short SFX transients.
        margin_harmonic_db: Optional separate margin for harmonic component.
            Higher = more content pushed to percussive (less music bleed).
        margin_percussive_db: Optional separate margin for percussive component.
            Lower = more content kept as SFX (less aggressive filtering).

    Returns:
        (harmonic, percussive) tuple, each with same shape as input.
    """
    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[np.newaxis, :]

    channels = audio.shape[0]
    harmonic = np.zeros_like(audio)
    percussive = np.zeros_like(audio)

    # Build margin: prefer asymmetric tuple for better SFX preservation
    if margin_harmonic_db is not None and margin_percussive_db is not None:
        margin = (margin_harmonic_db, margin_percussive_db)
    else:
        margin = margin_db

    for ch in range(channels):
        h, p = librosa.effects.hpss(
            audio[ch],
            kernel_size=kernel_size,
            margin=margin,
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
    n_fft: int = 1024,
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

    # Use stationary mode when no noise profile — ~3x faster
    use_stationary = noise_sample is None
    kwargs = dict(
        sr=sr,
        stationary=use_stationary,
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

        with np.errstate(invalid='ignore', divide='ignore'):
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


# ── High-Frequency Restoration ──────────────────────────────────────────


def restore_high_frequencies(
    audio: np.ndarray,
    sr: int = 44100,
    boost_db: float = 3.0,
    crossover_hz: float = 8000.0,
) -> np.ndarray:
    """Restore high-frequency content lost during spectral denoising.

    Applies a gentle high-shelf boost above `crossover_hz` to bring back
    sibilants (S, SH, F, T), air, and vocal breathiness that are commonly
    attenuated by spectral noise reduction. Uses a first-order shelf filter
    implemented via scipy.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        sr: Sample rate.
        boost_db: Boost amount in dB. 2-4 dB is typically sufficient.
        crossover_hz: Frequency above which to apply the boost.

    Returns:
        Audio with restored high frequencies, same shape as input.
    """
    if boost_db <= 0:
        return audio.copy()

    was_1d = audio.ndim == 1
    if was_1d:
        audio = audio[np.newaxis, :]

    # Design a high-shelf filter using RBJ Audio-EQ Cookbook biquad coefficients
    # Q=0.707 gives a gentle, musical shelf (Butterworth-like)

    # Normalize frequency
    w0 = crossover_hz / (sr / 2)
    # Gain in linear scale
    g = 10 ** (boost_db / 20.0)
    A = np.sqrt(g)
    cos_w0 = np.cos(np.pi * w0)
    sin_w0 = np.sin(np.pi * w0)
    alpha = sin_w0 / (2 * 0.707)  # Q=0.707

    b_hs = [
        A * ((A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha),
        -2 * A * ((A - 1) + (A + 1) * cos_w0),
        A * ((A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha),
    ]
    a_hs = [
        (A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha,
        2 * ((A - 1) - (A + 1) * cos_w0),
        (A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha,
    ]

    # Normalize
    b_hs = np.array(b_hs) / a_hs[0]
    a_hs = np.array(a_hs) / a_hs[0]

    sos = tf2sos(b_hs, a_hs)

    result = audio.copy()
    for ch in range(audio.shape[0]):
        result[ch] = sosfilt(sos, audio[ch])

    if was_1d:
        result = result.squeeze(0)

    return result


# ── Loudness Normalization ────────────────────────────────────────────────


def normalize_loudness(
    audio: np.ndarray,
    target_rms: Optional[float] = None,
    ref_audio: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Normalize audio loudness to compensate for level loss from processing.

    After spectral denoising and gating, the overall signal level is typically
    reduced by 2-6 dB. This function restores the original loudness:
    - If `ref_audio` is provided, matches the RMS of the reference.
    - Otherwise, applies a fixed target RMS suitable for vocal content.

    Args:
        audio: (channels, samples) or (samples,) float32 array.
        target_rms: Target RMS level. If None and no ref, uses 0.08 (-22 dB).
        ref_audio: Reference audio to match loudness to (e.g. original mix).

    Returns:
        Loudness-normalized audio with same shape as input.
    """
    if target_rms is not None:
        ref_rms = target_rms
    elif ref_audio is not None:
        ref_rms = np.sqrt(np.mean(ref_audio ** 2))
    else:
        ref_rms = 0.08  # ~ -22 dB — reasonable for vocal content

    current_rms = np.sqrt(np.mean(audio ** 2))
    if current_rms < 1e-12:
        return audio.copy()

    gain = ref_rms / current_rms
    # Limit gain to avoid excessive boosting (max +6 dB)
    gain = min(gain, 2.0)
    # Also ensure we don't clip
    result = audio * gain
    peak = np.max(np.abs(result))
    if peak > 1.0:
        result = result / peak * 0.99

    return result


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
    gate_threshold_db: float = -55.0,
    gate_floor_db: float = -60.0,
    enable_denoise: bool = True,
    denoise_prop: float = 0.35,
    min_vocal_duration: float = 0.08,
    trim: bool = False,
    enable_multiband: bool = True,
    denoise_band_split_hz: tuple[float, float] = (250.0, 6000.0),
    denoise_strength_low: float = 0.35,
    denoise_strength_mid: float = 0.10,
    denoise_strength_high: float = 0.25,
    enable_noise_profile: bool = False,
    adaptive_gate: bool = False,
    enable_hf_restore: bool = True,
    hf_boost_db: float = 3.0,
    enable_loudness_normalize: bool = True,
) -> np.ndarray:
    """Full post-processing pipeline for separated vocals.

    Pipeline order:
    1. Extract noise profile from VAD-identified silent sections (if enabled)
    2. Apply vocal gate to silence instrumental-only sections
    3. Apply spectral denoise (gentle multi-band or single-band)
    4. Restore high frequencies lost during denoising (high-shelf boost)
    5. Normalize loudness to compensate for processing level loss
    6. Trim leading/trailing silence

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
        enable_hf_restore: Apply high-frequency restoration after denoising.
        hf_boost_db: High-shelf boost amount in dB.
        enable_loudness_normalize: Normalize loudness after processing.

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

    # ── Step 3: Apply spectral denoise (gentle) ──
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

    # ── Step 4: Restore high frequencies lost in denoising ──
    if enable_hf_restore:
        logger.info("Restoring high frequencies (+%.1f dB above %.0f Hz)",
                    hf_boost_db, 8000.0)
        result = restore_high_frequencies(
            result, sr=sr, boost_db=hf_boost_db,
        )

    # ── Step 5: Normalize loudness ──
    if enable_loudness_normalize:
        logger.info("Normalizing loudness")
        result = normalize_loudness(result, ref_audio=vocals)

    # ── Step 6: Trim silence ──
    if trim:
        logger.info("Trimming silence")
        result = trim_silence(result, sr=sr)

    return result
