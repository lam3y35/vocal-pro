import queue
import threading
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def app():
    with patch("code.gui_app.ctk.CTk"), \
         patch("code.gui_app.ctk.set_appearance_mode"), \
         patch("code.gui_app.ctk.set_default_color_theme"), \
         patch("code.gui_app.load_config") as lc:
        lc.return_value = {
            "model_name": "htdemucs_ft", "output_format": "wav",
            "include_sfx": False, "enable_vocal_gate": True,
            "enable_spectral_denoise": True, "generate_comparison_samples": False,
            "save_background_track": False, "trim_silence": False,
            "ffmpeg_path": "", "segment": 16.0, "overlap": 0.5, "shifts": 1,
            "gate_threshold_db": -38, "denoise_strength": 0.75,
            "large_file_threshold_minutes": 15, "audio_bitrate": "320k",
            "ffmpeg_faststart": True, "device": "auto",
            "enable_multiband_denoise": True, "enable_noise_profile": True,
            "adaptive_gate_floor": True, "enable_sfx_separation": False,
            "ensemble_mode": False,
        }
        from code.gui_app import App
        a = App.__new__(App)
        a.config = lc.return_value
        a.queue = queue.Queue()
        a.input_files = []
        a._input_files_lock = threading.Lock()
        a._download_history = []
        a._separation_history = []
        a._last_url = None
        a._download_cancel = threading.Event()
        a._download_in_progress = False
        a.current_output_dir = None
        a.engine = None
        a.worker = None
        a._stem_sliders = {}
        a._stem_mixer_output_dir = None
        a._preview_thread = None
        a._is_playing = False
        a._stem_master_vol = MagicMock()
        a._wave_audio_data = None
        a._wave_sr = None
        a._wave_is_playing = False
        a._wave_paused = False
        a._wave_pos = 0
        a._wave_cursor_id = None
        a._wave_update_id = None
        for attr in ["drop_zone", "file_count_badge", "btn_start", "btn_cancel",
                     "btn_retry", "btn_cancel_dload", "btn_file", "btn_url",
                     "btn_clear", "btn_output_dir", "btn_reveal", "btn_advanced",
                     "btn_history", "btn_sep_history", "progress_bar",
                     "overall_progress", "log_text", "status_badge",
                     "output_dir_label", "model_desc_label",
                     "model_var", "format_var", "include_sfx_var",
                     "enable_gate_var", "enable_denoise_var", "gen_samples_var",
                     "save_bg_var", "trim_silence_var",
                     "enable_multiband_var", "enable_profile_var",
                     "adaptive_gate_var", "sfx_sep_var", "karaoke_var", "ensemble_var",
                     "bpm_label", "preset_var", "preset_menu",
                     "_stem_mixer_card", "_stem_slider_frame",
                     "_stem_master_label", "_btn_preview", "_btn_stop",
                     "_btn_export", "_btn_reset",
                     "_waveform_frame", "_waveform_canvas",
                     "_wave_play_btn", "_wave_stop_btn", "_wave_time_label"]:
            setattr(a, attr, MagicMock())
        a.after = MagicMock()
        for _var, _val in [("model_var", "htdemucs_ft"), ("format_var", "wav"),
                           ("include_sfx_var", False), ("enable_gate_var", True),
                           ("enable_denoise_var", True), ("gen_samples_var", False),
                           ("save_bg_var", False), ("trim_silence_var", False),
                           ("enable_multiband_var", True), ("enable_profile_var", True),
                            ("adaptive_gate_var", True), ("sfx_sep_var", False),
                            ("karaoke_var", False), ("ensemble_var", False),
                            ("preset_var", "")]:
            getattr(a, _var).get.return_value = _val
        a._model_descriptions = {"htdemucs_ft": "best", "mdx_extra": "robust"}
        yield a
