import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestUtils:
    def test_get_exe_none(self):
        from code.utils import _get_exe
        assert _get_exe("ffmpeg") == "ffmpeg"

    def test_get_exe_custom_missing(self):
        from code.utils import _get_exe
        with tempfile.TemporaryDirectory() as td:
            assert _get_exe("ffmpeg", td) == "ffmpeg"

    def test_get_exe_custom_found(self):
        from code.utils import _get_exe
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "ffmpeg.exe")
            Path(p).write_text("")
            assert _get_exe("ffmpeg", td) == p

    def test_check_ffmpeg_ok(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            assert check_ffmpeg() is True

    def test_check_ffmpeg_not_found(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert check_ffmpeg() is False

    def test_check_ffmpeg_fail(self):
        from code.utils import check_ffmpeg
        with patch("subprocess.run") as m:
            m.side_effect = subprocess.CalledProcessError(1, [])
            assert check_ffmpeg() is False

    def test_run_ffmpeg_ok(self):
        from code.utils import _run_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            _run_ffmpeg(["ffmpeg"])

    def test_run_ffmpeg_fail(self):
        from code.utils import _run_ffmpeg
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=1, stderr="err")
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                _run_ffmpeg(["ffmpeg"])

    def test_get_audio_info_sample(self):
        from code.utils import get_audio_info
        sr, dur = 44100, 0.5
        import soundfile as sf
        f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.close()
        try:
            t = np.linspace(0, dur, int(sr * dur), 0)
            sf.write(f.name, np.sin(2 * np.pi * 440 * t).astype(np.float32), sr)
            sr2, d2, ts, ch = get_audio_info(f.name)
            assert sr2 == 44100 and d2 == pytest.approx(0.5, abs=0.05) and ch in (1, 2)
        finally:
            os.unlink(f.name)

    def test_get_audio_info_no_audio(self):
        from code.utils import get_audio_info
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}))
            with pytest.raises(ValueError, match="No audio stream"):
                get_audio_info("x.mp4")

    def test_video_duration_found(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video", "duration": "10.5"}]}))
            assert get_video_duration("x.mp4") == 10.5

    def test_video_duration_none(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "audio"}]}))
            assert get_video_duration("x.mp4") is None

    def test_video_duration_frames(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            j = json.dumps({"streams": [{"codec_type": "video", "nb_frames": "300", "avg_frame_rate": "30/1"}]})
            m.return_value = MagicMock(returncode=0, stdout=j)
            assert get_video_duration("x.mp4") == 10.0

    def test_video_duration_no_data(self):
        from code.utils import get_video_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0, stdout=json.dumps({"streams": [{"codec_type": "video"}]}))
            assert get_video_duration("x.mp4") is None

    def test_trim_audio(self):
        from code.utils import trim_audio_to_duration
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False); f.close()
            try:
                trim_audio_to_duration("i.wav", f.name, 0.1)
                c = m.call_args[0][0]
                assert "-t" in c and any("0.1" in str(x) for x in c)
            finally:
                os.unlink(f.name)

    def test_mux_basic(self):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=10):
                mux_audio_video("i.mp4", "a.wav", "o.mp4")
                c = m.call_args[0][0]
                assert "0:v:0" in c and "1:a:0" in c
                # Must NOT have -t between inputs (Bug 1: old placement)
                assert c.index("-i") < c.index("a.wav")
                # Must have atrim+apad for sync
                assert any("atrim" in str(x) for x in c)
                assert any("apad" in str(x) for x in c)

    def test_mux_no_trim(self):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=None):
                mux_audio_video("i.mp4", "a.wav", "o.mp4", trim_to_video=False)
                c = m.call_args[0][0]
                assert m.called
                # When no video duration, no atrim/apad filter
                assert not any("atrim" in str(x) for x in c)

    def test_mux_sync_filter_uses_video_dur(self):
        from code.utils import mux_audio_video
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            with patch("code.utils.get_video_duration", return_value=60.5):
                mux_audio_video("i.mp4", "a.wav", "o.mp4")
                c = " ".join(m.call_args[0][0])
                assert "atrim=end=60.5" in c
                assert "apad=whole_dur=60.5" in c

    def test_extract_audio(self):
        from code.utils import extract_audio
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_audio("i.mp4", "o.wav")
            assert "-vn" in m.call_args[0][0]

    def test_extract_chunk(self):
        from code.utils import extract_chunk
        with patch("subprocess.run") as m:
            m.return_value = MagicMock(returncode=0)
            extract_chunk("i.wav", "o.wav", 10, 5)
            c = m.call_args[0][0]
            assert "-ss" in c and "-t" in c

    def test_format_size(self):
        from code.utils import format_size
        assert format_size(0) == "0.0 B"
        assert format_size(1023) == "1023.0 B"
        assert format_size(1024) == "1.0 KB"
        assert format_size(1048576) == "1.0 MB"
        assert format_size(1073741824) == "1.0 GB"
        assert format_size(1.5e9) == "1.4 GB"
        assert format_size(-100) == "-100.0 B"
