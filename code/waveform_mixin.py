"""VocalPro – Waveform logic."""

from __future__ import annotations

import os

import sounddevice as sd
import soundfile as sf

from code._shared import _ACCENT, _BORDER, _WARNING


class WaveformMixin:
    def _load_waveform(self, path: str) -> None:
        """Load audio file for waveform display and playback."""
        if self._wave_update_id:
            self.after_cancel(self._wave_update_id)
            self._wave_update_id = None
        self._wave_stop()
        try:
            data, sr = sf.read(path, dtype="float32")
            if data.ndim == 2:
                data = data.mean(axis=1)  # mono for display
            self._wave_audio_data = data
            self._wave_sr = sr
            self._wave_pos = 0
            self._wave_is_playing = False
            self._wave_paused = False
            self._draw_waveform()
            self._waveform_frame.pack(fill="x", pady=(4, 0))
            self._wave_time_label.configure(
                text=f"0:00 / {self._format_time(len(data) / sr)}"
            )
        except Exception as e:
            self.log(f"Could not load waveform: {e}")
            self._waveform_frame.pack_forget()

    def _draw_waveform(self) -> None:
        """Draw the waveform on the canvas."""
        if self._wave_audio_data is None:
            return
        data = self._wave_audio_data
        sr = self._wave_sr
        cw = self._waveform_canvas.winfo_width() or 600
        ch = 80
        self._waveform_canvas.delete("all")
        self._waveform_canvas.configure(height=ch)

        # Downsample to fit canvas width
        step = max(1, len(data) // cw)
        samples = data[::step]
        if len(samples) < 2:
            return

        # Normalize
        peak = max(abs(samples).max(), 1e-10)
        mid = ch / 2
        scale = (ch - 8) / 2 / peak

        coords = []
        for x, s in enumerate(samples):
            y = mid - s * scale
            coords.extend([x, y])
        if coords:
            self._waveform_canvas.create_line(
                *coords, fill=_ACCENT, width=1, smooth=True,
            )
            # Center line
            self._waveform_canvas.create_line(
                0, mid, len(samples), mid, fill=_BORDER, width=1, dash=(2, 4),
            )

        # Store for cursor positioning
        self._wave_draw_step = step
        self._wave_draw_len = len(samples)

    def _format_time(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}:{s:02d}"

    def _wave_play_pause(self) -> None:
        if self._wave_audio_data is None:
            return
        if self._wave_paused:
            self._wave_paused = False
            self._wave_play_btn.configure(text="⏸ Pause")
            self._wave_stop_btn.configure(state="normal")
        else:
            if self._wave_is_playing:
                sd.stop()
                self._wave_paused = True
                self._wave_play_btn.configure(text="▶ Play")
                return
            # Start fresh playback
            self._wave_is_playing = True
            self._wave_paused = False
            self._wave_pos = 0
            self._wave_play_btn.configure(text="⏸ Pause")
            self._wave_stop_btn.configure(state="normal")
            self._wave_cursor_update_loop()

        # Play from current position
        data = self._wave_audio_data
        sr = self._wave_sr
        start = self._wave_pos
        sd.play(data[start:], samplerate=sr)

    def _wave_stop(self) -> None:
        sd.stop()
        self._wave_is_playing = False
        self._wave_paused = False
        self._wave_pos = 0
        self._wave_play_btn.configure(text="▶ Play")
        self._wave_stop_btn.configure(state="disabled")
        if self._wave_cursor_id:
            self._waveform_canvas.delete(self._wave_cursor_id)
            self._wave_cursor_id = None
        if self._wave_update_id:
            self.after_cancel(self._wave_update_id)
            self._wave_update_id = None
        if self._wave_audio_data is not None and self._wave_sr:
            self._wave_time_label.configure(
                text=f"0:00 / {self._format_time(len(self._wave_audio_data) / self._wave_sr)}"
            )

    def _wave_cursor_update_loop(self) -> None:
        """Periodically update the playback cursor and time label."""
        if not self._wave_is_playing or self._wave_paused:
            return

        # Estimate current position from sounddevice's playback position
        try:
            pos = int(sd.get_stream().time * self._wave_sr) if sd.get_stream() else self._wave_pos
        except Exception:
            pos = self._wave_pos

        if pos >= len(self._wave_audio_data):
            self._wave_stop()
            return

        self._wave_pos = pos
        total_sec = len(self._wave_audio_data) / self._wave_sr
        cur_sec = pos / self._wave_sr
        self._wave_time_label.configure(
            text=f"{self._format_time(cur_sec)} / {self._format_time(total_sec)}"
        )

        # Update cursor position on waveform
        if self._wave_cursor_id:
            self._waveform_canvas.delete(self._wave_cursor_id)
        draw_x = pos / self._wave_draw_step
        self._wave_cursor_id = self._waveform_canvas.create_line(
            draw_x, 0, draw_x, self._waveform_canvas.winfo_height() or 80,
            fill=_WARNING, width=2,
        )

        self._wave_update_id = self.after(100, self._wave_cursor_update_loop)

