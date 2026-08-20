"""Audio separation engine using Demucs (Hybrid Transformer) models.

Manages model loading, device configuration, VRAM-aware segment sizing,
chunked processing for large files, crossfade merging, and post-processing
integration for vocal cleaning and SFX separation.
"""

import gc
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

import librosa
import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as F_ta
import copy

logger = logging.getLogger(__name__)
from demucs.pretrained import get_model as demucs_get_model

from code.audio_postprocess import postprocess_vocals, separate_sfx, smooth_crossfade_chunks
from code.utils import _get_exe, extract_audio, extract_chunk, get_audio_info, mux_audio_video


def _remove_with_retry(path: str, max_attempts: int = 3, delay: float = 0.2) -> None:
    """Remove a file with retry logic for Windows file-lock contention."""
    for _ in range(max_attempts):
        try:
            os.remove(path)
            return
        except OSError:
            time.sleep(delay)
    logger.warning("Failed to remove %s after %d attempts", path, max_attempts)


MODEL_POOL = frozenset({
    "htdemucs_ft",    # Best quality, fine-tuned, ~3.5GB VRAM
    "htdemucs",       # Base Hybrid Transformer (faster)
    "htdemucs_6s",    # 6-stem: adds piano + guitar separation
    "hdemucs_mmi",    # v3 Hybrid Demucs retrained
    "mdx",            # MDX Challenge track A winner
    "mdx_extra",      # MDX with extra augmentation data
    "mdx_q",          # Quantized — smaller, faster, slightly lower quality
    "mdx_extra_q",    # Quantized MDX with extra data, good for low VRAM
})

# Global model cache to avoid repeated downloads/instantiation. Keys are
# (model_name, device_type) -> {'model': nn.Module, 'refcount': int}
MODEL_CACHE = {}
MODEL_CACHE_LOCK = threading.Lock()

_GC_EVERY_N_SEGMENTS = 5


class SeparationEngine:
    """Main engine orchestrating audio/video separation with Demucs models."""

    def __init__(self, config, progress_callback=None, cancel_event=None):
        """Initialize engine: configure device, VRAM tuning, model loading."""

        self.config = dict(config)  # shallow copy to avoid mutating caller's dict
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event or threading.Event()
        device_pref = config.get("device", "auto")
        if device_pref == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        elif device_pref == "cuda":
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            else:
                self.device = torch.device("cpu")
                self.progress(0, "⚠️ CUDA requested but not available, falling back to CPU")
        else:
            self.device = torch.device(device_pref)

        # CUDA performance optimizations for high-performance GPUs
        if self.device.type == "cuda":
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.set_float32_matmul_precision('high')
            try:
                torch.backends.cudnn.deterministic = False
            except Exception:
                pass
        max_threads = self.config.get("max_threads", 0)
        if not max_threads or max_threads <= 0:
            max_threads = max(1, (os.cpu_count() or 1) - 1)  # use all cores except 1
        try:
            torch.set_num_threads(max_threads)
        except Exception:
            pass
        os.environ.setdefault("OMP_NUM_THREADS", str(max_threads))
        os.environ.setdefault("MKL_NUM_THREADS", str(max_threads))

        self.model = None
        self.model_name = None
        self.sample_rate = 44100
        self.cooldown_between_chunks = float(self.config.get("cooldown_between_chunks_seconds", 0.0))
        self.safe_mode = bool(self.config.get("safe_mode", False))
        # Lock to make model loads thread-safe
        self._load_lock = threading.Lock()

        # VRAM detection: auto-tune segment size and guard against low-VRAM GPUs
        if self.device.type == "cuda":
            try:
                vram_total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                if vram_total_gb < 3.0:
                    self.device = torch.device("cpu")
                    self.progress(0, "⚠️ VRAM <3 GB, falling back to CPU")
                else:
                    # Auto-scale segment length based on available VRAM
                    # Larger segments = fewer passes = faster processing
                    current_seg = float(self.config.get("segment", 16.0))
                    if vram_total_gb >= 12.0:
                        target_seg = 24.0   # plenty of VRAM, use large segments
                    elif vram_total_gb >= 8.0:
                        target_seg = 16.0   # good GPU, default sweet spot
                    elif vram_total_gb >= 6.0:
                        target_seg = 10.0   # moderate GPU
                    else:
                        target_seg = 6.0    # low VRAM but still on GPU
                    # Only increase segment (never decrease user's explicit choice)
                    if current_seg < target_seg:
                        self.config["segment"] = target_seg
                        self.progress(0, f"⚡ GPU {vram_total_gb:.1f} GB VRAM – segment={target_seg:.0f}s")
            except Exception:
                pass

        # ── CPU safety defaults (user can override in advanced settings) ──
        # When running on CPU, some GPU-heavy defaults would take prohibitively
        # long. We set conservative defaults but DO NOT override the user's
        # explicit choices for model, shifts, or segment.
        if self.device.type == "cpu":
            cpu_model = self.config.get("model_name", "htdemucs_ft")
            # Warn about potentially slow models but respect user's choice.
            CPU_HEAVY = {"htdemucs_ft", "htdemucs_6s", "hdemucs_mmi", "mdx", "mdx_extra"}
            if cpu_model in CPU_HEAVY:
                self.progress(0, f"⚠️ '{cpu_model}' on CPU will be slow — switch to mdx_q or htdemucs for faster processing")
            # Set safe CPU defaults (user can override via advanced settings)
            current_shifts = int(self.config.get("shifts", 5))
            if current_shifts > 1:
                self.config["shifts"] = 1
                self.progress(0, "⚡ CPU – shifts defaulted to 1 (change in Advanced Settings if needed)")
            current_seg = float(self.config.get("segment", 24.0))
            if current_seg > 6.0:
                self.config["segment"] = 6.0
                self.progress(0, "⚡ CPU – segment defaulted to 6s (change in Advanced Settings if needed)")

        # If safe_mode is enabled, cap segment length to a conservative value
        # regardless of device type (applies to both CPU and CUDA). This ensures
        # low-VRAM GPUs also respect safe_mode.
        if self.safe_mode:
            try:
                self.config["segment"] = float(min(6.0, float(self.config.get("segment", 6.0))))
            except Exception:
                self.config["segment"] = 6.0

        self._load_model()

    def update_config(self, new_config):
        """Update engine configuration without full re-initialization if possible."""
        old_model = self.config.get("model_name")
        self.config.update(new_config)
        new_model = self.config.get("model_name")
        
        if old_model != new_model:
            self._load_model()
        
        # Re-check VRAM scaling if model changed
        if self.device.type == "cuda" and old_model != new_model:
            try:
                vram_total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                current_seg = float(self.config.get("segment", 16.0))
                if vram_total_gb >= 12.0: target_seg = 24.0
                elif vram_total_gb >= 8.0: target_seg = 16.0
                elif vram_total_gb >= 6.0: target_seg = 10.0
                else: target_seg = 6.0
                if current_seg < target_seg:
                    self.config["segment"] = target_seg
            except Exception:
                pass

    # ------------------------------------------------------------------
    def _release_model(self):
        # Decrement refcount in global cache for current model/device and remove if zero
        try:
            key = (self.model_name, self.device.type if self.device is not None else 'cpu')
            with MODEL_CACHE_LOCK:
                entry = MODEL_CACHE.get(key)
                if entry:
                    entry['refcount'] = max(0, entry.get('refcount', 1) - 1)
                    if entry['refcount'] == 0:
                        try:
                            del MODEL_CACHE[key]
                        except Exception:
                            pass
        except Exception:
            pass

    def __del__(self):
        try:
            self._release_model()
        except Exception:
            pass

    def _load_model(self):
        import contextlib
        model_name = self.config.get("model_name", "htdemucs_ft")
        if model_name not in MODEL_POOL:
            model_name = "htdemucs_ft"

        # Use a lock so concurrent callers cannot race model loads
        with self._load_lock:
            # If already loaded and matches, ensure it's on the right device
            if self.model is not None and self.model_name == model_name:
                try:
                    # ensure parameters live on desired device
                    first_param = next(self.model.parameters(), None)
                    if first_param is not None and first_param.device != self.device:
                        try:
                            self.model = self.model.to(self.device)
                        except Exception:
                            # best-effort; continue
                            pass
                except Exception:
                    pass
                return

            # If a cached model exists for this model+device, reuse it
            cache_key = (model_name, self.device.type if self.device is not None else 'cpu')
            with MODEL_CACHE_LOCK:
                entry = MODEL_CACHE.get(cache_key)
                if entry:
                    entry['refcount'] = entry.get('refcount', 0) + 1
                    self.model = entry['model']
                    self.model_name = model_name
                    self.progress(0, f"Reusing cached model '{model_name}' on {self.device.type}")
                    return

            # If a CPU cached model exists, try to deepcopy and move to desired device
            cpu_key = (model_name, 'cpu')
            with MODEL_CACHE_LOCK:
                cpu_entry = MODEL_CACHE.get(cpu_key)
            if cpu_entry and self.device.type != 'cpu':
                try:
                    model = copy.deepcopy(cpu_entry['model'])
                    try:
                        model = model.to(self.device)
                    except Exception:
                        model = model.to(torch.device('cpu'))
                        self.device = torch.device('cpu')
                    with MODEL_CACHE_LOCK:
                        MODEL_CACHE[cache_key] = {'model': model, 'refcount': 1}
                    self.model = model
                    self.model_name = model_name
                    self.progress(0, f"Instantiated model '{model_name}' from CPU cache to {self.device.type}")
                    return
                except Exception:
                    # fallback to full load
                    pass

            # Free old model before loading new one to avoid OOM / decrement refcount
            if self.model is not None:
                try:
                    # release from cache if we were holding it
                    self._release_model()
                except Exception:
                    pass
                try:
                    del self.model
                except Exception:
                    pass
                self.model = None
                gc.collect()
                if self.device.type == "cuda":
                    try:
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

            self.progress(0, f"Loading model '{model_name}' (downloading if needed)...")

            stderr_buf = io.StringIO()
            try:
                # Capture demucs download stderr so failures are visible
                with contextlib.redirect_stderr(stderr_buf):
                    model = demucs_get_model(model_name)
            except Exception as e:
                err = stderr_buf.getvalue()
                logger.exception("Failed to download/load demucs model %s: %s\nStderr: %s", model_name, e, err)
                self.progress(0, f"Failed to load model '{model_name}': {e}")
                raise

            # Move model to the configured device; if it fails, fall back to CPU
            try:
                model = model.to(self.device)
            except Exception as e:
                logger.warning("Moving model to device %s failed: %s. Falling back to CPU.", self.device, e)
                try:
                    model = model.to(torch.device("cpu"))
                except Exception:
                    # last resort, keep original model
                    pass
                self.device = torch.device("cpu")

            # Put model in eval mode and freeze parameters to reduce memory
            try:
                model.eval()
            except Exception:
                pass
            try:
                for p in model.parameters():
                    try:
                        p.requires_grad = False
                    except Exception:
                        pass
            except Exception:
                pass

            # Try to pick up a sample rate from the model if available
            sr = None
            try:
                sr = getattr(model, 'samplerate', None) or getattr(model, 'sample_rate', None) or getattr(model, 'sr', None)
                # Only accept numeric sample rates to avoid MagicMock/Falsey traps in tests
                if isinstance(sr, (int, float)) and sr > 0:
                    self.sample_rate = int(sr)
            except Exception:
                pass

            # Configure sub-models robustly (BagOfModels or other wrappers)
            from demucs.apply import BagOfModels
            models_to_configure = []
            try:
                if isinstance(model, BagOfModels):
                    models_to_configure = list(model.models)
                else:
                    m_attr = getattr(model, 'models', None)
                    if m_attr:
                        try:
                            models_to_configure = list(m_attr)
                        except Exception:
                            models_to_configure = [model]
                    else:
                        # If it's an nn.Module, try children(); else use the model itself
                        try:
                            children = list(model.children())
                            models_to_configure = children if children else [model]
                        except Exception:
                            models_to_configure = [model]
            except Exception:
                models_to_configure = [model]

            seg = self.config.get("segment")
            try:
                segf = float(seg) if seg is not None else None
            except Exception:
                segf = None

            for m in models_to_configure:
                try:
                    if hasattr(m, 'use_train_segment'):
                        try:
                            m.use_train_segment = False
                        except Exception:
                            pass
                    if segf is not None and hasattr(m, 'segment'):
                        try:
                            m.segment = segf
                        except Exception:
                            logger.debug("Could not set segment on model %s", getattr(m, '__class__', m))
                except Exception:
                    # silence per-model config errors but continue
                    logger.debug("Ignoring model configuration error for %s", getattr(m, '__class__', m))

            # Store in cache for reuse
            cache_key = (model_name, self.device.type if self.device is not None else 'cpu')
            with MODEL_CACHE_LOCK:
                MODEL_CACHE[cache_key] = {'model': model, 'refcount': 1}

            self.model = model
            self.model_name = model_name
            self.progress(0, f"Model '{model_name}' ready.")

    # ------------------------------------------------------------------
    def _check_cancel(self):
        if self.cancel_event.is_set():
            raise InterruptedError("Operation cancelled")

    def progress(self, percent, msg=""):
        """Report progress callback with optional VRAM usage info on CUDA."""

        vram_info = ""
        if self.device.type == "cuda":
            try:
                # Use reserved memory which is more stable for progress reporting
                reserved = torch.cuda.memory_reserved(0) / (1024 ** 3)
                total = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                vram_info = f" [VRAM: {reserved:.1f}/{total:.1f} GB]"
            except Exception:
                pass
        
        if self.progress_callback is not None:
            self.progress_callback(percent, f"{msg}{vram_info}")

    def _has_video_stream(self, file_path):
        ffprobe_exe = _get_exe("ffprobe", self.config.get("ffmpeg_path"))
        try:
            cmd = [
                ffprobe_exe, "-v", "quiet", "-print_format", "json",
                "-show_streams", file_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as e:
            logger.warning("ffprobe not available or failed for %s: %s", file_path, e)
            return False
        if res.returncode != 0:
            logger.warning("ffprobe failed (exit %d) for %s: %s",
                            res.returncode, file_path, res.stderr.strip())
            return False
        try:
            streams = json.loads(res.stdout).get("streams", [])
        except json.JSONDecodeError as e:
            logger.warning("ffprobe output parse failed for %s: %s", file_path, e)
            return False
        return any(s.get("codec_type") == "video" for s in streams)

    def _resample_tensor(self, audio: torch.Tensor, orig_freq: int, new_freq: int) -> torch.Tensor:
        """Resample using torchaudio (fast, GPU capable). Falls back to librosa on error."""
        try:
            return F_ta.resample(audio, orig_freq, new_freq)
        except Exception:
            # fallback to librosa – audio is (channels, samples) after transpose
            np_audio = audio.cpu().numpy()
            resampled = librosa.resample(np_audio, orig_sr=orig_freq, target_sr=new_freq)
            return torch.from_numpy(resampled).to(audio.device)

    # ------------------------------------------------------------------
    def separate_file(self, input_path, output_dir):
        """Separate a full audio/video file into vocals and background stems.

        Orchestrates the full pipeline through focused sub-methods:
            1. _prepare_input  – video detection, audio extraction, temp dir setup
            2. _run_separation – model inference (standard, large-file, or ensemble)
            3. _postprocess_and_save – vocal cleaning, karaoke, format conversion, mixing
            4. _finalize_output – duration normalization, video muxing, comparison samples
        """
        self._check_cancel()

        # Early progress: model is already loaded in __init__, so report a
        # real value immediately so the UI doesn't sit at 0% during the
        # audio extraction / preparation phase.
        self.progress(5, f"Model '{self.model_name}' loaded, preparing audio...")

        ff_path = self.config.get("ffmpeg_path")
        tmpdir = tempfile.mkdtemp()
        try:
            # ── Step 1: Prepare input ──
            is_video, wav_path, file_output_dir, base_name, sr, duration, total_samples, channels, is_large = (
                self._prepare_input(input_path, output_dir, ff_path, tmpdir)
            )
            self.progress(10, "Audio prepared, starting separation...")
            # ── Step 2: Run separation ──
            result = self._run_separation(
                is_large, wav_path, file_output_dir, total_samples, sr, channels,
            )
            # ── Step 3: Post-process & save outputs ──
            final_audio_path = self._postprocess_and_save(
                result, file_output_dir, base_name, sr, ff_path,
            )
            # ── Step 4: Finalize (normalize, mux, samples) ──
            final_output_path = self._finalize_output(
                input_path, final_audio_path, file_output_dir, base_name,
                is_video, duration, sr, wav_path, ff_path,
            )
            self.progress(100, "Separation complete!")
            return final_output_path
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    def _prepare_input(self, input_path, output_dir, ff_path, tmpdir):
        """Detect video streams, extract audio, create output folder.

        Returns:
            (is_video, wav_path, file_output_dir, base_name, sr, duration,
             total_samples, channels, is_large)
        """
        is_video = self._has_video_stream(input_path)
        self.progress(0, "Video file detected – output will include MP4" if is_video
                      else "Audio file detected – output will be WAV only")

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        base_name = re.sub(r'[<>:\"/\\\\|?*]', '_', base_name)
        file_output_dir = os.path.join(output_dir, base_name)
        os.makedirs(file_output_dir, exist_ok=True)

        sr, duration, total_samples, channels = get_audio_info(input_path, ffmpeg_path=ff_path)
        large_thresh = self.config.get("large_file_threshold_minutes", 15) * 60
        is_large = duration > large_thresh

        if not is_large:
            wav_path = os.path.join(tmpdir, "full_audio.wav")
            extract_audio(input_path, wav_path, ffmpeg_path=ff_path)
        else:
            wav_path = input_path
            self.progress(1, "Large file detected – chunked processing")

        return (is_video, wav_path, file_output_dir, base_name, sr,
                duration, total_samples, channels, is_large)

    # ------------------------------------------------------------------
    def _run_separation(self, is_large, wav_path, file_output_dir,
                        total_samples, sr, channels):
        """Execute model inference – standard, large-file chunked, or ensemble mode.

        Returns a dict with stem arrays (keyed by stem name) plus optional
        ``_vocals_array`` (in-memory, large-file) and ``other_path`` (file path).
        """
        if is_large:
            ensemble = self.config.get("ensemble_mode", False)
            if ensemble:
                self.progress(1, "Ensemble skipped for large files – using single model")
            return self._separate_large_file(wav_path, file_output_dir,
                                              total_samples, sr, channels)

        ensemble = self.config.get("ensemble_mode", False)
        if not ensemble:
            self.progress(1, "Starting standard separation...")
            return self._run_demucs_on_file(wav_path, progress_offset=5, progress_scale=85)

        # ── Ensemble mode: average two models ──
        ensemble_models = ["htdemucs_ft", "mdx_extra"]
        self.progress(1, f"Ensemble mode: {', '.join(ensemble_models)}")
        original_model_name = self.config.get("model_name", "htdemucs_ft")
        combined = None
        count = 0
        try:
            for em_i, em_model in enumerate(ensemble_models):
                if self.cancel_event and self.cancel_event.is_set():
                    break
                self.progress(5 + em_i * 40,
                              f"Running {em_model} ({em_i + 1}/{len(ensemble_models)})...")
                self.config["model_name"] = em_model
                self._load_model()
                em_result = self._run_demucs_on_file(
                    wav_path, progress_offset=10 + em_i * 40, progress_scale=35,
                )
                if combined is None:
                    combined = em_result
                else:
                    for key in em_result:
                        if (key in combined
                                and isinstance(em_result[key], np.ndarray)
                                and isinstance(combined[key], np.ndarray)):
                            min_len = min(combined[key].shape[-1], em_result[key].shape[-1])
                            combined[key] = combined[key][:, :min_len] + em_result[key][:, :min_len]
                    count += 1
            if combined is not None and count > 0:
                for key in combined:
                    if isinstance(combined[key], np.ndarray):
                        combined[key] /= (count + 1)
                return combined
            self._check_cancel()
            return combined or {}
        finally:
            self.config["model_name"] = original_model_name
            self._load_model()

    # ------------------------------------------------------------------
    def _postprocess_and_save(self, result, file_output_dir, base_name, sr, ff_path):
        """Extract vocals from result, apply post-processing (gate/denoise/trim),
        handle karaoke mode, convert output format, save background track,
        and optionally mix vocals with SFX.

        Returns the path to the final processed audio file.
        """
        if not isinstance(result, dict):
            raise RuntimeError("Separation produced no result")

        vocals_wav_path = os.path.join(file_output_dir, f"{base_name}_vocals.wav")

        # ── Extract arrays ──
        vocals_array = result.get("_vocals_array") or result.get("vocals")
        other_array = result.get("other")
        other_path = result.get("other_path")

        enable_gate = self.config.get("enable_vocal_gate", True)
        enable_denoise = self.config.get("enable_spectral_denoise", True)
        trim_silence = self.config.get("trim_silence", False)
        save_bg = self.config.get("save_background_track", False)
        enable_sfx_sep = self.config.get("enable_sfx_separation", False)

        # ── Write / move vocals file ──
        if isinstance(vocals_array, np.ndarray):
            if not (enable_gate or enable_denoise or trim_silence):
                sf.write(vocals_wav_path, vocals_array.T, self.sample_rate)
        elif isinstance(vocals_array, str) and os.path.exists(vocals_array):
            if os.path.abspath(vocals_array) != os.path.abspath(vocals_wav_path):
                try:
                    shutil.move(vocals_array, vocals_wav_path)
                except Exception:
                    shutil.copy2(vocals_array, vocals_wav_path)
                    _remove_with_retry(vocals_array)
            else:
                vocals_wav_path = vocals_array
        else:
            raise RuntimeError("Separation did not produce a vocals track")

        # ── Karaoke: sum all non-vocal stems ──
        karaoke = self.config.get("karaoke_mode", False)
        if karaoke:
            try:
                karaoke_mix = None
                for src_name, src_data in result.items():
                    if src_name == "vocals" or not isinstance(src_data, np.ndarray):
                        continue
                    if karaoke_mix is None:
                        karaoke_mix = np.zeros_like(src_data)
                        karaoke_mix[:src_data.shape[0], :src_data.shape[1]] += src_data
                    else:
                        mc = min(karaoke_mix.shape[0], src_data.shape[0])
                        ms = min(karaoke_mix.shape[1], src_data.shape[1])
                        karaoke_mix[:mc, :ms] += src_data[:mc, :ms]
                if karaoke_mix is not None:
                    karaoke_path = os.path.join(file_output_dir, f"{base_name}_karaoke.wav")
                    sf.write(karaoke_path, karaoke_mix.T, self.sample_rate)
                    self.progress(94, "🎤 Karaoke instrumental saved.")
                    del karaoke_mix
                gc.collect()
            except Exception as e:
                self.progress(94, f"Karaoke mix error: {e}")

        # ── Post-processing (gate + denoise + trim) ──
        if enable_gate or enable_denoise or trim_silence:
            if not isinstance(vocals_array, np.ndarray) and os.path.exists(vocals_wav_path):
                vocals_array, _ = sf.read(vocals_wav_path, dtype="float32")
                if vocals_array.ndim == 1:
                    vocals_array = vocals_array[:, np.newaxis]
                else:
                    vocals_array = vocals_array.T
            if isinstance(vocals_array, np.ndarray):
                self.progress(93, "Cleaning vocals…")
                vocals_array = postprocess_vocals(
                    vocals_array, sr=self.sample_rate,
                    enable_gate=enable_gate,
                    gate_threshold_db=self.config.get("gate_threshold_db", -40.0),
                    gate_floor_db=self.config.get("gate_floor_db", -60.0),
                    enable_denoise=enable_denoise,
                    denoise_prop=self.config.get("denoise_strength", 0.55),
                    min_vocal_duration=self.config.get("min_vocal_duration", 0.08),
                    trim=trim_silence,
                    enable_multiband=self.config.get("enable_multiband_denoise", False),
                    denoise_band_split_hz=self.config.get("denoise_band_split_hz", [250.0, 6000.0]),
                    denoise_strength_low=self.config.get("denoise_strength_low", 0.35),
                    denoise_strength_mid=self.config.get("denoise_strength_mid", 0.10),
                    denoise_strength_high=self.config.get("denoise_strength_high", 0.25),
                    enable_noise_profile=self.config.get("enable_noise_profile", False),
                    adaptive_gate=self.config.get("adaptive_gate_floor", False),
                )
                sf.write(vocals_wav_path, vocals_array.T, self.sample_rate)

            # Also denoise the "other" stem — only when it's actually used
            # (saves a full postprocess_vocals call when neither are enabled)
            if isinstance(other_array, np.ndarray) and enable_denoise and (save_bg or enable_sfx_sep):
                self.progress(93, "Cleaning background track…")
                other_array = postprocess_vocals(
                    other_array, sr=self.sample_rate,
                    enable_gate=False, enable_denoise=True,
                    denoise_prop=self.config.get("denoise_strength", 0.55),
                    trim=False,
                    enable_multiband=self.config.get("enable_multiband_denoise", False),
                    denoise_band_split_hz=self.config.get("denoise_band_split_hz", [250.0, 6000.0]),
                    denoise_strength_low=self.config.get("denoise_strength_low", 0.35),
                    denoise_strength_mid=self.config.get("denoise_strength_mid", 0.10),
                    denoise_strength_high=self.config.get("denoise_strength_high", 0.25),
                    enable_noise_profile=False, adaptive_gate=False,
                )

        # ── SFX separation on "other" stem ──
        other_sfx = None
        if enable_sfx_sep and isinstance(other_array, np.ndarray):
            self.progress(93, "Separating sound effects from music…")
            _music, other_sfx = separate_sfx(
                other_array, sr=self.sample_rate,
                margin_db=self.config.get("sfx_separation_margin_db", 5.0),
            )
            # No standalone sound_effects.wav — SFX is mixed into the main output below
            del _music

        # ── Output format conversion ──
        out_fmt = self.config.get("output_format", "wav").lower()
        if out_fmt != "wav":
            self.progress(95, f"Converting to {out_fmt.upper()}…")
            new_path = os.path.join(file_output_dir, f"{base_name}_vocals.{out_fmt}")
            try:
                subprocess.run([
                    _get_exe("ffmpeg", ff_path), "-y", "-i", vocals_wav_path,
                    "-b:a", self.config.get("audio_bitrate", "320k"), new_path,
                ], capture_output=True, check=True)
                _remove_with_retry(vocals_wav_path)
                vocals_wav_path = new_path
            except Exception as e:
                self.progress(95, f"Conversion error: {e}")

        # ── Save background track ──
        if save_bg:
            bg_path = os.path.join(file_output_dir, f"{base_name}_background.wav")
            if other_path and os.path.exists(other_path):
                try:
                    shutil.move(other_path, bg_path)
                except Exception:
                    shutil.copy2(other_path, bg_path)
                    _remove_with_retry(other_path)
                other_path = None
            elif isinstance(other_array, np.ndarray):
                sf.write(bg_path, other_array.T, self.sample_rate)
            self.progress(96, "Background track saved.")

        # ── Mix SFX into the vocals output ──
        # SFX is never saved as a standalone file. Instead, the extracted
        # percussive component is mixed directly into the vocals file.
        # In karaoke/song mode, the SFX is already naturally present in the
        # karaoke mix (via the raw "other" stem), so no re-mixing is needed.
        final_audio_path = vocals_wav_path
        include_sfx = self.config.get("include_sfx", True)
        if other_sfx is not None and include_sfx and not self.config.get("karaoke_mode", False):
            try:
                self.progress(95, "Mixing sound effects into vocals…")
                voc_data, _ = sf.read(final_audio_path, dtype="float32")
                if voc_data.ndim == 1:
                    voc_data = voc_data[:, None]
                sfx_data = other_sfx.T
                if sfx_data.ndim == 1:
                    sfx_data = sfx_data[:, None]
                min_len = min(voc_data.shape[0], sfx_data.shape[0])
                voc_data = voc_data[:min_len] + sfx_data[:min_len]
                sf.write(final_audio_path, voc_data, self.sample_rate)
                del voc_data
                self.progress(96, "✓ Sound effects mixed into vocals.")
            except Exception as e:
                self.progress(96, f"SFX mix error: {e}")

        # ── Cleanup result & temp stems ──
        if other_path and os.path.exists(other_path):
            _remove_with_retry(other_path)
        if isinstance(other_array, np.ndarray):
            del other_array
        gc.collect()
        return final_audio_path

    # ------------------------------------------------------------------
    def _finalize_output(self, input_path, final_audio_path, file_output_dir,
                         base_name, is_video, duration, sr, wav_path, ff_path):
        """Normalize audio duration to match the original, handle video muxing
        (video_only / audio_only / both), and generate comparison samples.

        Returns the path to the final deliverable (muxed video or audio file).
        """
        # ── Normalize duration ──
        expected = int(duration * self.sample_rate)
        try:
            data, data_sr = sf.read(final_audio_path, dtype="float32")
            if data_sr != self.sample_rate:
                data = librosa.resample(data.T, orig_sr=data_sr, target_sr=self.sample_rate).T
                data_sr = self.sample_rate
            actual = data.shape[0]
            if actual > expected:
                data = data[:expected]
            elif actual < expected:
                pad = expected - actual
                data = np.pad(data, ((0, pad), (0, 0)) if data.ndim > 1 else (0, pad), mode="constant")
            if actual != expected:
                sf.write(final_audio_path, data, self.sample_rate)
                self.progress(98, "Audio duration normalized for sync")
        except Exception:
            pass

        # ── Video muxing ──
        video_mode = self.config.get("video_output_mode", "both")
        input_ext = os.path.splitext(input_path)[1].lower()
        is_input_video = input_ext in {'.mp4', '.mkv', '.avi', '.mov', '.flv'}

        if not is_input_video:
            return final_audio_path  # audio in → no muxing possible

        output_path = final_audio_path

        if video_mode == "video_only":
            output_path = self._mux_single(
                input_path, final_audio_path, file_output_dir, base_name, ff_path,
            )
            # Remove standalone audio file to keep only muxed video
            try:
                if os.path.exists(final_audio_path):
                    _remove_with_retry(final_audio_path)
            except Exception:
                pass
        elif video_mode == "both":
            output_path = self._mux_single(
                input_path, final_audio_path, file_output_dir, base_name, ff_path,
            )
        # else audio_only: skip mux, keep audio file as-is

        # ── Comparison samples ──
        if self.config.get("generate_comparison_samples", False):
            try:
                voc_arr = None
                voc_candidate = os.path.join(file_output_dir, f"{base_name}_vocals.wav")
                if os.path.exists(voc_candidate):
                    voc_arr = voc_candidate
                self._generate_comparison_samples(
                    wav_path, voc_arr, file_output_dir, base_name, sr, duration,
                )
            except Exception as e:
                self.progress(99, f"Samples error: {e}")

        return output_path

    # ------------------------------------------------------------------
    def _mux_single(self, video_input, audio_wav, output_dir, base_name, ff_path):
        """Mux separated audio back onto the original video. Returns muxed path."""
        try:
            self.progress(98, "Creating final video...")
            output_path = os.path.join(output_dir, f"{base_name}_clean.mp4")
            mux_audio_video(
                video_input=video_input,
                audio_wav=audio_wav,
                output_path=output_path,
                audio_bitrate=self.config.get("audio_bitrate", "320k"),
                ffmpeg_faststart=self.config.get("ffmpeg_faststart", True),
                trim_to_video=True,
                ffmpeg_path=ff_path,
            )
            self.progress(99, "Video created.")
            return output_path
        except Exception as e:
            self.progress(99, f"Video mux error: {e}")
            return audio_wav

    # ------------------------------------------------------------------
    def _separate_large_file(self, wav_path, output_dir, total_samples, sr, channels):
        chunk_min = self.config.get("chunk_duration_minutes", 12)
        overlap_sec = self.config.get("overlap_seconds", 5)
        chunk_samples = int(chunk_min * 60 * sr)
        overlap_samples = int(overlap_sec * sr)
        hop = chunk_samples - overlap_samples
        if hop <= 0:
            hop = max(1, chunk_samples // 2)
            overlap_samples = chunk_samples - hop
        num_chunks = max(1, int(np.ceil((total_samples - overlap_samples) / hop)))

        save_bg = self.config.get("save_background_track", False)
        include_sfx = self.config.get("include_sfx", False)
        need_other = save_bg or include_sfx

        ff_path = self.config.get("ffmpeg_path")

        self.progress(3, f"Splitting into {num_chunks} chunks...")
        tmp_chunks_dir = tempfile.mkdtemp()
        chunk_paths = []
        _temp_paths = []
        try:
            for i in range(num_chunks):
                start_sec = (i * hop) / sr
                dur = chunk_samples / sr
                chunk_wav = os.path.join(tmp_chunks_dir, f"chunk_{i:04d}.wav")
                extract_chunk(wav_path, chunk_wav, start_sec, dur, ffmpeg_path=ff_path, channels=channels)
                chunk_paths.append(chunk_wav)
                self.progress(4 + (i + 1) / num_chunks * 40, f"Chunk {i+1}/{num_chunks}")

            vocal_arrays = []
            other_arrays = [] if need_other else None

            for i, chunk_file in enumerate(chunk_paths):
                self._check_cancel()
                self.progress(44 + (i + 1) / num_chunks * 40, f"Processing chunk {i+1}/{num_chunks}")
                result = self._run_demucs_on_file(chunk_file)
                vocal_arrays.append(result['vocals'])
                if need_other and 'other' in result:
                    other_arrays.append(result['other'])
                del result
                if i % _GC_EVERY_N_SEGMENTS == 0:
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                if self.cooldown_between_chunks > 0:
                    time.sleep(self.cooldown_between_chunks)

            self.progress(90, "Merging chunks with smooth crossfade…")
            
            # Merge vocals
            merged_voc = smooth_crossfade_chunks(
                [v.T for v in vocal_arrays],
                overlap_samples=overlap_samples,
                sr=sr,
            )
            v_fd, v_path = tempfile.mkstemp(suffix="_merged_vocals.wav")
            os.close(v_fd)
            sf.write(v_path, merged_voc, self.sample_rate)
            del vocal_arrays
            gc.collect()
            
            # Keep merged_voc alive — caller uses it directly for
            # post-processing to avoid reading the WAV back from disk.
            # Transpose to (channels, samples) to match the expected
            # shape convention of the rest of the pipeline.
            final_result = {'vocals': v_path, '_vocals_array': merged_voc.T}

            # Merge other (background) if needed
            if need_other and other_arrays:
                self.progress(91, "Merging background track…")
                merged_other = smooth_crossfade_chunks(
                    [o.T for o in other_arrays],
                    overlap_samples=overlap_samples,
                    sr=sr,
                )
                o_fd, o_path = tempfile.mkstemp(suffix="_merged_other.wav")
                os.close(o_fd)
                sf.write(o_path, merged_other, self.sample_rate)
                del other_arrays
                gc.collect()
                # Do NOT append o_path to _temp_paths: caller manages cleanup of the returned other_path
                final_result['other_path'] = o_path

            return final_result
        finally:
            shutil.rmtree(tmp_chunks_dir, ignore_errors=True)
            for _p in _temp_paths:
                if os.path.exists(_p):
                    _remove_with_retry(_p)

    # ------------------------------------------------------------------
    def _run_demucs_on_file(self, wav_path, progress_offset=5, progress_scale=85):
        """Return dict with 'vocals' and 'other' as numpy arrays (channels, samples).
        
        Uses demucs.apply.apply_model which handles segmentation, overlap-add,
        normalization, and shift averaging internally.
        
        Spawns a subprocess that periodically pushes estimated progress to the
        API server via HTTP (bypasses the GIL, which would block a daemon thread
        during PyTorch CPU inference).
        """
        from demucs.apply import apply_model

        audio_np, sr = sf.read(wav_path, dtype="float32")
        audio_t = torch.from_numpy(audio_np).T.unsqueeze(0).to(self.device)  # (1, ch, samples)
        if sr != self.sample_rate:
            audio_t = self._resample_tensor(audio_t, sr, self.sample_rate)

        shifts = int(self.config.get("shifts", 3))

        total_frames = audio_t.shape[2]
        audio_duration = total_frames / self.sample_rate
        start_time = time.perf_counter()

        self.progress(progress_offset, "Separating audio...")

        # ── Granular progress estimation subprocess ─────────────────────────
        # apply_model doesn't expose a callback, and PyTorch CPU inference
        # holds the GIL (blocking daemon threads). Instead we spawn a subprocess
        # that sends HTTP requests to the API server -- no GIL contention.
        #
        # Expected runtime: audio_duration * speed_factor * shifts
        #   CPU (htdemucs): ~1.7x realtime × shifts
        #   GPU (htdemucs_ft): ~0.15x realtime × shifts
        if self.device.type == "cuda":
            estimated_seconds = audio_duration * 0.15 * max(1, shifts)
        else:
            estimated_seconds = audio_duration * 1.7 * max(1, shifts)

        # Only spawn the subprocess if we have a job_id configured
        est_proc = None
        job_id = self.config.get("_job_id")
        if job_id and estimated_seconds > 3:
            server_url = "http://127.0.0.1:8000"
            # Use \n delimiters to keep each statement on its own line and avoid
            # the "compound statement after ;" syntax error in Python's grammar.
            nl = "\n"
            script = (
                "import time, urllib.request, json" + nl +
                f"t0=time.time()" + nl +
                f"est={estimated_seconds}" + nl +
                f"off={progress_offset}" + nl +
                f"sc={progress_scale}" + nl +
                f"jid='{job_id}'" + nl +
                f"url='{server_url}'" + nl +
                "while True:" + nl +
                "    el=time.time()-t0" + nl +
                "    if el>est*1.5: break" + nl +
                "    pct=off+min(el/max(est,1),0.90)*sc" + nl +
                "    try:" + nl +
                "        msg='Separating '+str(round(el))+'s/~'+str(round(est))+'s'" + nl +
                "        data=json.dumps({'percent':round(pct,1),'message':msg}).encode()" + nl +
                "        req=urllib.request.Request(url+'/api/jobs/'+jid+'/progress',data=data,headers={'Content-Type':'application/json'})" + nl +
                "        urllib.request.urlopen(req,timeout=2)" + nl +
                "    except:" + nl +
                "        pass" + nl +
                "    time.sleep(3)" + nl
            )
            try:
                est_proc = subprocess.Popen(
                    [sys.executable, "-c", script],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                est_proc = None

        try:
            with torch.inference_mode():
                try:
                    stems = apply_model(
                        self.model,
                        audio_t,
                        split=True,
                        overlap=0.25,
                        shifts=shifts,
                        device=self.device,
                        segment=self.config.get("segment") or None,
                        progress=False,
                        num_workers=0,
                    )
                except torch.cuda.OutOfMemoryError:
                    self.progress(progress_offset, "⚠️ GPU out-of-memory, freeing cache and retrying…")
                    del audio_t
                    torch.cuda.empty_cache()
                    gc.collect()
                    raise RuntimeError(
                        "GPU ran out of memory. Try: a smaller model (mdx_q), "
                        "lower 'segment' in Advanced Settings, or switch to CPU."
                    )
                except RuntimeError as e:
                    if "CUDA" in str(e) or "cuda" in str(e):
                        del audio_t
                        torch.cuda.empty_cache()
                        gc.collect()
                        raise RuntimeError(
                            f"CUDA error during separation: {e}\n"
                            "Try switching to CPU in Advanced Settings."
                        )
                    raise
        finally:
            # Kill the subprocess if still running
            if est_proc is not None:
                try:
                    est_proc.kill()
                    est_proc.wait(timeout=2)
                except Exception:
                    pass

        del audio_t
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # stems shape: (1, sources, ch, samples)
        sources = self.model.sources

        # Return ALL stems for karaoke mode mixing
        result = {}
        for i, src in enumerate(sources):
            result[src] = stems[0, i, :, :total_frames].cpu().numpy()

        elapsed = time.perf_counter() - start_time
        self.progress(progress_offset + progress_scale, f"Done – {elapsed:.0f}s")

        del stems
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return result

    # ------------------------------------------------------------------
    def _generate_comparison_samples(
        self, original_wav_path, vocals_array, output_dir, base_name, sr, duration,
    ):
        """Extract 3 random short clips from the original and separated vocals
        and save them side by side in a ``samples/`` subfolder for easy comparison.

        Memory-efficient: avoids writing a full temporary vocals file when the
        separated vocals are already available in-memory as a numpy array.
        """
        import random

        sample_duration = min(5.0, duration / 4)
        if sample_duration < 1.0:
            self.progress(99, "File too short for comparison samples")
            return

        samples_dir = os.path.join(output_dir, "samples")
        os.makedirs(samples_dir, exist_ok=True)

        # vocals_array can be either a path to a WAV or an ndarray (channels, samples)
        voc_array_is_nd = isinstance(vocals_array, np.ndarray)
        voc_path_to_read = None

        if not voc_array_is_nd:
            if isinstance(vocals_array, str) and os.path.exists(vocals_array):
                voc_path_to_read = vocals_array
            else:
                # If a canonical vocals file exists in output_dir, prefer that
                existing_voc_path = os.path.join(output_dir, f"{base_name}_vocals.wav")
                if os.path.exists(existing_voc_path):
                    voc_path_to_read = existing_voc_path
                else:
                    self.progress(99, "Cannot generate samples – vocals not available")
                    return

        try:
            # Pick 3 random start positions
            n_frames = int(sample_duration * sr)
            total_frames = int(duration * sr)
            max_start = max(0, total_frames - n_frames)

            # Divide file into 3 regions and pick one sample from each for better coverage
            region_size = max_start // 3
            starts = []
            for i in range(3):
                r_start = i * region_size
                r_end = (i + 1) * region_size if i < 2 else max_start
                if r_start < r_end:
                    starts.append(random.randint(r_start, r_end))
                else:
                    starts.append(r_start)

            for idx, start_frame in enumerate(starts):
                # Read original clip from disk
                clip_orig, _ = sf.read(original_wav_path, start=start_frame, frames=n_frames, dtype="float32")

                # Obtain vocals clip either from in-memory array or from the vocals file
                if voc_array_is_nd:
                    # vocals_array expected shape: (channels, samples) or (samples,)
                    if vocals_array.ndim == 1:
                        clip_voc = vocals_array[start_frame : start_frame + n_frames]
                    else:
                        clip_voc = vocals_array[:, start_frame : start_frame + n_frames].T
                else:
                    clip_voc, _ = sf.read(voc_path_to_read, start=start_frame, frames=n_frames, dtype="float32")

                sf.write(os.path.join(samples_dir, f"sample_{idx + 1}_music.wav"), clip_orig, sr)
                sf.write(os.path.join(samples_dir, f"sample_{idx + 1}_no_music.wav"), clip_voc, sr)

            self.progress(99, f"✓ 3 comparison samples saved to samples/")
        finally:
            # nothing to clean up when using the in-memory path
            return

    # Note: shift averaging is handled internally by demucs.apply.apply_model
