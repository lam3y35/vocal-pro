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
import sys
import tempfile
import threading
import time

import librosa
import numpy as np
import soundfile as sf
import torch
import torchaudio
import torchaudio.functional as F_ta

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

        if self.safe_mode and self.device.type != "cuda":
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
    def _load_model(self):
        import contextlib
        model_name = self.config.get("model_name", "htdemucs_ft")
        if model_name not in MODEL_POOL:
            model_name = "htdemucs_ft"
        if self.model is not None and self.model_name == model_name:
            return
        # Free old model before loading new one to avoid OOM
        if self.model is not None:
            del self.model
            self.model = None
            gc.collect()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()
        self.progress(0, f"Loading model '{model_name}' (downloading if needed)...")
        # Suppress tqdm progress bars from demucs download to stderr
        with contextlib.redirect_stderr(io.StringIO()):
            self.model = demucs_get_model(model_name).to(self.device)
        self.model.eval()
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
        cmd = [
            ffprobe_exe, "-v", "quiet", "-print_format", "json",
            "-show_streams", file_path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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
        """Separate a full audio/video file into vocals and background stems."""

        self._check_cancel()

        ff_path = self.config.get("ffmpeg_path")

        is_video = self._has_video_stream(input_path)
        output_video = self.config.get("output_video", True) and is_video
        if is_video:
            self.progress(0, "Video file detected – output will include MP4")
        else:
            self.progress(0, "Audio file detected – output will be WAV only")

        # Create a per-file subfolder inside the output directory
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        # Sanitize folder name: replace chars invalid on Windows
        base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
        file_output_dir = os.path.join(output_dir, base_name)
        os.makedirs(file_output_dir, exist_ok=True)

        tmpdir = tempfile.mkdtemp()
        try:
            # Check file size BEFORE extraction to avoid wasted I/O for large files
            sr, duration, total_samples, channels = get_audio_info(input_path, ffmpeg_path=ff_path)
            large_thresh = self.config.get("large_file_threshold_minutes", 15) * 60
            is_large = duration > large_thresh

            if not is_large:
                wav_path = os.path.join(tmpdir, "full_audio.wav")
                extract_audio(input_path, wav_path, ffmpeg_path=ff_path)
            else:
                wav_path = input_path  # _separate_large_file chunks from source directly
                self.progress(1, "Large file detected – chunked processing")

            ensemble_mode = self.config.get("ensemble_mode", False)

            if is_large:
                if ensemble_mode:
                    self.progress(1, "Ensemble skipped for large files – using single model")
                result = self._separate_large_file(wav_path, file_output_dir, total_samples, sr, channels)
            else:
                if ensemble_mode:
                    ensemble_models = ["htdemucs_ft", "mdx_extra"]
                    self.progress(1, f"Ensemble mode: {', '.join(ensemble_models)}")
                    original_model_name = self.config.get("model_name", "htdemucs_ft")
                    combined = None
                    count = 0
                    for em_i, em_model in enumerate(ensemble_models):
                        if self.cancel_event and self.cancel_event.is_set():
                            break
                        self.progress(5 + em_i * 40, f"Running {em_model} ({em_i + 1}/{len(ensemble_models)})...")
                        self.config["model_name"] = em_model
                        self._load_model()
                        em_result = self._run_demucs_on_file(wav_path, progress_offset=10 + em_i * 40, progress_scale=35)
                        if combined is None:
                            combined = em_result
                        else:
                            for key in em_result:
                                if key in combined and isinstance(em_result[key], np.ndarray) and isinstance(combined[key], np.ndarray):
                                    min_len = min(combined[key].shape[-1], em_result[key].shape[-1])
                                    combined[key] = combined[key][:, :min_len] + em_result[key][:, :min_len]
                            count += 1
                    if combined is not None and count > 0:
                        for key in combined:
                            if isinstance(combined[key], np.ndarray):
                                combined[key] = combined[key] / (count + 1)
                        result = combined
                    else:
                        result = combined or {}
                    self.config["model_name"] = original_model_name
                    self._load_model()
                else:
                    self.progress(1, "Starting standard separation...")
                    result = self._run_demucs_on_file(wav_path, progress_offset=5, progress_scale=85)

            vocals_wav_path = os.path.join(file_output_dir, f"{base_name}_vocals.wav")

            # Handle result: could be dict from _run_demucs_on_file or string from _separate_large_file
            vocals_array = None
            other_array = None

            if not isinstance(result, dict):
                raise RuntimeError("Separation produced no result")

            vocals_array = result.get("vocals")
            other_array = result.get("other")
            other_path = result.get("other_path")  # For large files

            if isinstance(vocals_array, np.ndarray):
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

            # ---------- Post-processing: vocal gate + spectral denoise ----------
            enable_gate = self.config.get("enable_vocal_gate", True)
            enable_denoise = self.config.get("enable_spectral_denoise", True)
            trim_silence = self.config.get("trim_silence", False)
            save_bg = self.config.get("save_background_track", False)
            enable_sfx_sep = self.config.get("enable_sfx_separation", False)
            karaoke_mode = self.config.get("karaoke_mode", False)
            
            if enable_gate or enable_denoise or trim_silence:
                # Ensure we have vocals as a numpy array
                if not isinstance(vocals_array, np.ndarray) and os.path.exists(vocals_wav_path):
                    vocals_array, _ = sf.read(vocals_wav_path, dtype="float32")
                    if vocals_array.ndim == 1:
                        vocals_array = vocals_array[:, np.newaxis]
                    else:
                        vocals_array = vocals_array.T  # (samples, ch) -> (ch, samples)
                
                if isinstance(vocals_array, np.ndarray):
                    self.progress(93, "Cleaning vocals…")
                    vocals_array = postprocess_vocals(
                        vocals_array, sr=self.sample_rate,
                        enable_gate=enable_gate,
                        gate_threshold_db=self.config.get("gate_threshold_db", -40.0),
                        gate_floor_db=self.config.get("gate_floor_db", -60.0),
                        enable_denoise=enable_denoise,
                        denoise_prop=self.config.get("denoise_strength", 0.85),
                        min_vocal_duration=self.config.get("min_vocal_duration", 0.1),
                        trim=trim_silence,
                        enable_multiband=self.config.get("enable_multiband_denoise", True),
                        denoise_band_split_hz=self.config.get("denoise_band_split_hz", [250.0, 6000.0]),
                        denoise_strength_low=self.config.get("denoise_strength_low", 0.90),
                        denoise_strength_mid=self.config.get("denoise_strength_mid", 0.65),
                        denoise_strength_high=self.config.get("denoise_strength_high", 0.80),
                        enable_noise_profile=self.config.get("enable_noise_profile", True),
                        adaptive_gate=self.config.get("adaptive_gate_floor", True),
                    )
                    sf.write(vocals_wav_path, vocals_array.T, self.sample_rate)
                    
                    # Also post-process the "other" stem if available
                    other_music = None
                    other_sfx = None
                    if isinstance(other_array, np.ndarray):
                        if enable_denoise:
                            self.progress(93, "Cleaning background track…")
                            other_d = postprocess_vocals(
                                other_array, sr=self.sample_rate,
                                enable_gate=False,
                                enable_denoise=True,
                                denoise_prop=self.config.get("denoise_strength", 0.85),
                                trim=False,
                                enable_multiband=self.config.get("enable_multiband_denoise", True),
                                denoise_band_split_hz=self.config.get("denoise_band_split_hz", [250.0, 6000.0]),
                                denoise_strength_low=self.config.get("denoise_strength_low", 0.90),
                                denoise_strength_mid=self.config.get("denoise_strength_mid", 0.65),
                                denoise_strength_high=self.config.get("denoise_strength_high", 0.80),
                                enable_noise_profile=False,
                                adaptive_gate=False,
                            )
                            other_array = other_d
                        
                        # SFX separation: split "other" stem into music (harmonic) + SFX (percussive)
                        if enable_sfx_sep:
                            self.progress(93, "Separating sound effects from music…")
                            other_music, other_sfx = separate_sfx(
                                other_array, sr=self.sample_rate,
                                margin_db=self.config.get("sfx_separation_margin_db", 5.0),
                            )
                            sf.write(
                                os.path.join(file_output_dir, f"{base_name}_music.wav"),
                                other_music.T, self.sample_rate,
                            )
                            sf.write(
                                os.path.join(file_output_dir, f"{base_name}_sound_effects.wav"),
                                other_sfx.T, self.sample_rate,
                            )
                            self.progress(93, "Music and SFX saved separately.")
                        
                        if save_bg:
                            sf.write(
                                os.path.join(file_output_dir, f"{base_name}_background.wav"),
                                other_array.T, self.sample_rate,
                            )

            # ---------- Karaoke Instrumental: sum all non-vocal stems ----------
            if karaoke_mode and isinstance(result, dict):
                try:
                    karaoke = None
                    for src_name, src_data in result.items():
                        if src_name == "vocals":
                            continue
                        if isinstance(src_data, np.ndarray):
                            if karaoke is None:
                                karaoke = src_data.copy()
                            else:
                                min_ch = min(karaoke.shape[0], src_data.shape[0])
                                min_samp = min(karaoke.shape[1], src_data.shape[1])
                                karaoke = karaoke[:min_ch, :min_samp] + src_data[:min_ch, :min_samp]
                    if karaoke is not None:
                        karaoke_path = os.path.join(file_output_dir, f"{base_name}_karaoke.wav")
                        sf.write(karaoke_path, karaoke.T, self.sample_rate)
                        self.progress(94, "🎤 Karaoke instrumental saved.")
                except Exception as e:
                    self.progress(94, f"Karaoke mix error: {e}")

            # ---------- Handle Output Format Conversion ----------
            out_fmt = self.config.get("output_format", "wav").lower()
            if out_fmt != "wav":
                self.progress(95, f"Converting to {out_fmt.upper()}…")
                new_vocals_path = os.path.join(file_output_dir, f"{base_name}_vocals.{out_fmt}")
                try:
                    # Use FFmpeg for conversion (higher quality/more formats)
                    cmd = [
                        _get_exe("ffmpeg", ff_path), "-y", "-i", vocals_wav_path,
                        "-b:a", self.config.get("audio_bitrate", "320k"),
                        new_vocals_path
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                    _remove_with_retry(vocals_wav_path)
                    vocals_wav_path = new_vocals_path
                except Exception as e:
                    self.progress(95, f"Conversion error: {e}")

            # ---------- Save the "other" stem (background music) only if requested ----------
            sfx_path = None
            
            # For large files, other_path is used. For small files, other_array is used.
            if other_path and os.path.exists(other_path):
                if save_bg:
                    sfx_path = os.path.join(file_output_dir, f"{base_name}_background.wav")
                    try:
                        shutil.move(other_path, sfx_path)
                    except Exception:
                        shutil.copy2(other_path, sfx_path)
                        _remove_with_retry(other_path)
                    self.progress(96, "Background track saved.")
                else:
                    # If not saving, we still might need it for mixing
                    sfx_path = other_path
                    self.progress(96, "Background track processed.")

            elif isinstance(other_array, np.ndarray):
                if save_bg:
                    sfx_path = os.path.join(file_output_dir, f"{base_name}_background.wav")
                    sf.write(sfx_path, other_array.T, self.sample_rate)
                    self.progress(96, "Background track saved.")
                else:
                    self.progress(96, "Background track skipped (not requested).")

            # ---------- Optional: mix vocals + SFX (or music) into a combined file ----------
            final_audio_path = vocals_wav_path
            include_sfx = self.config.get("include_sfx", False)
            
            if include_sfx:
                try:
                    voc_audio, _ = sf.read(vocals_wav_path, dtype="float32")
                    
                    mix_source = None
                    # If SFX separation was active, use only the percussive (SFX) part
                    if enable_sfx_sep and other_sfx is not None:
                        mix_source = other_sfx.T
                        mix_label = "Vocals + Sound Effects"
                        mix_filename = f"{base_name}_vocals_sfx_mix.wav"
                    elif sfx_path and os.path.exists(sfx_path):
                        mix_source, _ = sf.read(sfx_path, dtype="float32")
                        mix_label = "Vocals + Background"
                        mix_filename = f"{base_name}_vocals_background_mix.wav"
                    elif isinstance(other_array, np.ndarray):
                        mix_source = other_array.T
                        mix_label = "Vocals + Background"
                        mix_filename = f"{base_name}_vocals_background_mix.wav"
                    
                    if mix_source is not None:
                        if voc_audio.ndim == 1:
                            voc_audio = voc_audio[:, None]
                        if mix_source.ndim == 1:
                            mix_source = mix_source[:, None]
                        
                        min_len = min(voc_audio.shape[0], mix_source.shape[0])
                        mixed = voc_audio[:min_len] + mix_source[:min_len]
                        
                        mixed_path = os.path.join(file_output_dir, mix_filename)
                        sf.write(mixed_path, mixed, self.sample_rate)
                        final_audio_path = mixed_path
                        self.progress(97, f"✓ {mix_label} mix saved.")
                        del mixed
                except Exception as e:
                    self.progress(97, f"Mix error: {e}")

            # Cleanup
            if other_path and os.path.exists(other_path):
                _remove_with_retry(other_path)
            if isinstance(other_array, np.ndarray):
                del other_array
                gc.collect()

            # ---------- Normalize audio duration to prevent sync drift ----------
            # trim_silence can change length; demucs segment overlap can too.
            # Pad with silence or trim so the audio exactly matches the original.
            expected_samples = int(duration * self.sample_rate)
            try:
                data, data_sr = sf.read(final_audio_path, dtype="float32")
                if data_sr != self.sample_rate:
                    data = librosa.resample(data.T, orig_sr=data_sr, target_sr=self.sample_rate).T
                    data_sr = self.sample_rate
                actual = data.shape[0]
                if actual > expected_samples:
                    data = data[:expected_samples]
                elif actual < expected_samples:
                    pad_len = expected_samples - actual
                    if data.ndim == 1:
                        data = np.pad(data, (0, pad_len), mode="constant")
                    else:
                        data = np.pad(data, ((0, pad_len), (0, 0)), mode="constant")
                if actual != expected_samples:
                    sf.write(final_audio_path, data, self.sample_rate)
                    self.progress(98, "Audio duration normalized for sync")
            except Exception:
                pass

            # ---------- Mux with video if needed ----------
            if output_video:
                self.progress(98, "Creating final video...")
                output_video_path = os.path.join(file_output_dir, f"{base_name}_clean.mp4")
                mux_audio_video(
                    video_input=input_path,
                    audio_wav=final_audio_path,
                    output_path=output_video_path,
                    audio_bitrate=self.config.get("audio_bitrate", "320k"),
                    ffmpeg_faststart=self.config.get("ffmpeg_faststart", True),
                    trim_to_video=True,
                    ffmpeg_path=self.config.get("ffmpeg_path"),
                )
                final_output_path = output_video_path
                self.progress(99, "Video created.")
            else:
                final_output_path = final_audio_path

            # ---------- Comparison samples: 3 random clips original vs vocals ----------
            generate_samples = self.config.get("generate_comparison_samples", False)
            if generate_samples:
                try:
                    self._generate_comparison_samples(
                        wav_path, vocals_array, file_output_dir, base_name, sr, duration,
                    )
                except Exception as e:
                    self.progress(99, f"Samples error: {e}")

            self.progress(100, "Separation complete!")
            return final_output_path
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

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
        try:
            for i in range(num_chunks):
                start_sec = (i * hop) / sr
                dur = chunk_samples / sr
                chunk_wav = os.path.join(tmp_chunks_dir, f"chunk_{i:04d}.wav")
                extract_chunk(wav_path, chunk_wav, start_sec, dur, ffmpeg_path=ff_path)
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
            sf.write(v_path, merged_voc, sr)
            del merged_voc, vocal_arrays
            gc.collect()
            
            final_result = {'vocals': v_path}

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
                sf.write(o_path, merged_other, sr)
                del merged_other, other_arrays
                gc.collect()
                final_result['other_path'] = o_path

            return final_result
        finally:
            shutil.rmtree(tmp_chunks_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    def _run_demucs_on_file(self, wav_path, progress_offset=5, progress_scale=85):
        """Return dict with 'vocals' and 'other' as numpy arrays (channels, samples).
        
        Uses demucs.apply.apply_model which handles segmentation, overlap-add,
        normalization, and shift averaging internally.
        """
        from demucs.apply import apply_model

        audio_np, sr = sf.read(wav_path, dtype="float32")
        audio_t = torch.from_numpy(audio_np).T.unsqueeze(0).to(self.device)  # (1, ch, samples)
        if sr != self.sample_rate:
            audio_t = self._resample_tensor(audio_t, sr, self.sample_rate)

        shifts = int(self.config.get("shifts", 3))

        total_frames = audio_t.shape[2]
        start_time = time.perf_counter()

        self.progress(progress_offset, "Separating audio...")

        with torch.inference_mode():
            try:
                stems = apply_model(
                    self.model,
                    audio_t,
                    split=True,
                    overlap=0.25,
                    shifts=shifts,
                    device=self.device,
                    segment=None,
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

        Memory-efficient: reads only the required clips from disk.
        """
        import random

        sample_duration = min(5.0, duration / 4)
        if sample_duration < 1.0:
            self.progress(99, "File too short for comparison samples")
            return

        samples_dir = os.path.join(output_dir, "samples")
        os.makedirs(samples_dir, exist_ok=True)

        # We need a path to the vocals to read clips without loading the whole array.
        # If vocals_array is already a file path, use it. Otherwise, write it to a temp file.
        voc_path_to_read = None
        temp_voc_path = None
        if isinstance(vocals_array, str) and os.path.exists(vocals_array):
            voc_path_to_read = vocals_array
        elif isinstance(vocals_array, np.ndarray):
            fd, temp_voc_path = tempfile.mkstemp(suffix="_voc_sample_tmp.wav")
            os.close(fd)
            sf.write(temp_voc_path, vocals_array.T, sr)
            voc_path_to_read = temp_voc_path
        
        if not voc_path_to_read:
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
                # Read original clip
                clip_orig, _ = sf.read(original_wav_path, start=start_frame, frames=n_frames, dtype="float32")
                # Read vocals clip
                clip_voc, _ = sf.read(voc_path_to_read, start=start_frame, frames=n_frames, dtype="float32")

                sf.write(
                    os.path.join(samples_dir, f"sample_{idx + 1}_music.wav"),
                    clip_orig, sr,
                )
                sf.write(
                    os.path.join(samples_dir, f"sample_{idx + 1}_no_music.wav"),
                    clip_voc, sr,
                )

            self.progress(99, f"✓ 3 comparison samples saved to samples/")
        finally:
            if temp_voc_path and os.path.exists(temp_voc_path):
                _remove_with_retry(temp_voc_path)

    # Note: shift averaging is handled internally by demucs.apply.apply_model

