"""Audio/video utility functions wrapping ffmpeg for file operations."""

import os
import json
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

# Shared default ffmpeg encoding parameters
_FFMPEG_DEFAULTS = ["-ar", "44100", "-ac", "2"]


def _get_exe(exe_name: str, custom_path: Optional[str] = None) -> str:
    """Return the full path to an ffmpeg/ffprobe executable."""
    if custom_path and os.path.isdir(custom_path):
        full_path = os.path.join(custom_path, exe_name)
        if os.name == "nt" and not full_path.lower().endswith(".exe"):
            full_path += ".exe"
        if os.path.isfile(full_path):
            return full_path
    return exe_name


def check_ffmpeg(custom_path: Optional[str] = None) -> bool:
    """Return True if ffmpeg is available on PATH or custom_path."""
    exe = _get_exe("ffmpeg", custom_path)
    try:
        subprocess.run(
            [exe, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=10,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _run_ffmpeg(cmd: list[str], description: str = "ffmpeg", timeout: int = 600) -> None:
    """Run an ffmpeg/ffprobe command and raise on failure with the stderr message.
    The first element of cmd should already be resolved via _get_exe if needed.
    """
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        stderr_msg = result.stderr.strip() or "(no output)"
        raise RuntimeError(f"{description} failed (exit {result.returncode}): {stderr_msg}")


def _run_ffprobe(file_path: str, ffmpeg_path: Optional[str] = None, extra_args: Optional[list[str]] = None) -> dict:
    exe = _get_exe("ffprobe", ffmpeg_path)
    cmd = [exe, "-v", "quiet", "-print_format", "json"]
    if extra_args:
        cmd.extend(extra_args)
    cmd.append(file_path)
    result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(result.stdout)


def get_audio_info(file_path: str, ffmpeg_path: Optional[str] = None) -> tuple[int, float, int, int]:
    """Return (sample_rate, duration_seconds, total_samples, channels)."""
    data = _run_ffprobe(file_path, ffmpeg_path, ["-show_format", "-show_streams"])
    streams = data.get("streams", [])
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not audio_stream:
        raise ValueError("No audio stream found")
    sample_rate = int(audio_stream.get("sample_rate", 44100))
    channels = int(audio_stream.get("channels", 2))
    duration = float(data["format"]["duration"])
    total_samples = int(duration * sample_rate)
    return sample_rate, duration, total_samples, channels


def get_video_duration(file_path: str, ffmpeg_path: Optional[str] = None) -> Optional[float]:
    """Return duration in seconds of the video stream, or None if no video."""
    data = _run_ffprobe(file_path, ffmpeg_path, ["-show_streams"])
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video_stream:
        return None
    # Prefer stream duration (more accurate than container duration)
    dur = video_stream.get("duration")
    if dur:
        return float(dur)
    # Fallback: nb_frames / avg_frame_rate
    nb_frames = video_stream.get("nb_frames")
    avg_frame_rate = video_stream.get("avg_frame_rate", "0/1")
    if nb_frames and avg_frame_rate and "/" in avg_frame_rate:
        num, den = avg_frame_rate.split("/")
        num_i, den_i = int(num), int(den)
        if den_i != 0 and num_i != 0:
            return int(nb_frames) / (num_i / den_i)
    return None


def trim_audio_to_duration(input_wav: str, output_wav: str, duration_sec: float, ffmpeg_path: Optional[str] = None) -> None:
    """Trim an audio file to exactly *duration_sec* seconds."""
    exe = _get_exe("ffmpeg", ffmpeg_path)
    cmd = [
        exe, "-y", "-i", input_wav,
        "-t", str(duration_sec),
        "-c:a", "pcm_f32le",
        *_FFMPEG_DEFAULTS,
        output_wav,
    ]
    _run_ffmpeg(cmd, "trim_audio_to_duration")


def mux_audio_video(
    video_input: str,
    audio_wav: str,
    output_path: str,
    audio_bitrate: str = "256k",
    ffmpeg_faststart: bool = True,
    trim_to_video: bool = True,
    ffmpeg_path: Optional[str] = None,
) -> None:
    """Mux clean audio onto original video with sample-accurate sync.

    Uses atrim+apad to guarantee the output audio duration exactly matches
    the video, preventing the drift that was happening with the old -t placement.
    """
    video_dur = get_video_duration(video_input, ffmpeg_path) if trim_to_video else None
    exe = _get_exe("ffmpeg", ffmpeg_path)

    cmd = [exe, "-y", "-i", video_input, "-i", audio_wav]

    cmd += [
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
    ]

    if video_dur is not None:
        # Trim audio to video duration (if longer) and pad with silence (if shorter).
        # This guarantees sample-accurate sync throughout the entire file.
        cmd += ["-af", f"atrim=end={video_dur},apad=whole_dur={video_dur}"]

    cmd += ["-shortest"]

    if ffmpeg_faststart:
        cmd += ["-movflags", "+faststart"]

    cmd.append(output_path)
    _run_ffmpeg(cmd, "mux_audio_video")


def extract_audio(input_path: str, output_wav_path: str, ffmpeg_path: Optional[str] = None) -> None:
    """Extract audio as WAV (float32 stereo 44100 Hz)."""
    exe = _get_exe("ffmpeg", ffmpeg_path)
    cmd = [
        exe, "-y", "-i", input_path,
        "-vn", "-acodec", "pcm_f32le",
        *_FFMPEG_DEFAULTS,
        output_wav_path,
    ]
    _run_ffmpeg(cmd, "extract_audio")


def extract_chunk(input_wav: str, output_chunk: str, start_sec: float, duration_sec: float, ffmpeg_path: Optional[str] = None) -> None:
    """Extract a chunk from an already-extracted WAV file."""
    exe = _get_exe("ffmpeg", ffmpeg_path)
    cmd = [
        exe, "-y",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", input_wav,
        "-c:a", "pcm_f32le",
        *_FFMPEG_DEFAULTS,
        output_chunk,
    ]
    _run_ffmpeg(cmd, "extract_chunk")
