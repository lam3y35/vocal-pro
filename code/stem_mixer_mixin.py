"""VocalPro – StemMixer logic."""

from __future__ import annotations

import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog

import librosa
import numpy as np
import soundfile as sf

import customtkinter as ctk

from code._shared import (
    _CARD_TOP, _TEXT, _TEXT_DIM,
    GhostButton,
)
from code.config import save_config
from code.utils import check_ffmpeg


class StemMixerMixin:
    def _populate_stem_mixer(self, output_dir: str) -> None:
        """Scan output_dir for stem files and build mixer controls."""
        self._stem_mixer_output_dir = output_dir
        # Clear existing sliders
        for w in self._stem_slider_frame.winfo_children():
            w.destroy()
        self._stem_sliders = {}

        base_names = self._detect_stems(output_dir)
        if not base_names:
            return

        for i, (stem_key, stem_label, stem_path) in enumerate(base_names):
            row = ctk.CTkFrame(self._stem_slider_frame, fg_color="transparent")
            row.pack(fill="x", pady=1)

            color = ["#7C3AED", "#22C55E", "#F59E0B", "#EF4444", "#3B82F6", "#EC4899"][i % 6]

            lbl = ctk.CTkLabel(
                row, text=f"{stem_label}:", width=70,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=color, anchor="w",
            )
            lbl.pack(side="left")

            var = tk.DoubleVar(value=100.0)
            slider = ctk.CTkSlider(
                row, from_=0, to=200, number_of_steps=200,
                variable=var,
                width=160, height=14,
                fg_color=_CARD_TOP, progress_color=color, button_color=color,
            )
            slider.pack(side="left", padx=(6, 4))

            pct_lbl = ctk.CTkLabel(
                row, text="100%",
                font=ctk.CTkFont(size=9), text_color=_TEXT_DIM, width=32,
            )
            pct_lbl.pack(side="left")

            # MIDI extraction button for melodic stems
            is_melodic = stem_key in ("vocals", "guitar", "piano", "bass")
            if is_melodic:
                GhostButton(
                    row, text="🎵 MIDI", width=52, height=20,
                    font=ctk.CTkFont(size=9),
                    command=lambda p=stem_path, n=stem_label: self._stem_to_midi(p, n),
                ).pack(side="right", padx=(0, 2))

            self._stem_sliders[stem_key] = {
                "var": var, "slider": slider, "label": pct_lbl,
                "path": stem_path, "name": stem_label,
            }

        self._stem_mixer_card.grid()
        self.log(f"Stem Mixer ready — {len(base_names)} stems loaded.")

    def _detect_stems(self, output_dir: str) -> list:
        """Find stem files in the output directory."""
        # Common stem suffixes produced by Demucs
        stem_suffixes = {
            "vocals": "Vocals", "drums": "Drums", "bass": "Bass",
            "other": "Other", "guitar": "Guitar", "piano": "Piano",
        }
        found = []
        for f in sorted(os.listdir(output_dir)):
            f_lower = f.lower()
            for suffix, label in stem_suffixes.items():
                if suffix in f_lower and f.endswith((".wav", ".mp3", ".flac")):
                    found.append((suffix, label, os.path.join(output_dir, f)))
                    break
        return found

    def _stem_reset(self) -> None:
        """Reset all stem volumes to 100%."""
        self._stem_master_vol.set(100.0)
        self._stem_master_label.configure(text="100%")
        for info in self._stem_sliders.values():
            info["var"].set(100.0)
            info["label"].configure(text="100%")

    def _update_stem_master_labels(self) -> None:
        pct = round(self._stem_master_vol.get())
        self._stem_master_label.configure(text=f"{pct}%")

    def _stem_preview(self) -> None:
        """Mix stems at current volume levels and play a short preview."""
        if self._is_playing:
            return
        self._is_playing = True
        self._btn_preview.configure(state="disabled")
        self._btn_stop.configure(state="normal")

        def _play():
            try:
                master_gain = self._stem_master_vol.get() / 100.0
                # Build list of (audio_data, gain) for each stem
                mixed = None
                sr = None
                for key, info in self._stem_sliders.items():
                    gain = info["var"].get() / 100.0 * master_gain
                    if gain < 0.01:
                        continue
                    data, file_sr = sf.read(info["path"], dtype="float32")
                    if sr is None:
                        sr = file_sr
                    if data.ndim == 1:
                        data = data.reshape(-1, 1)
                    if mixed is None:
                        mixed = data * gain
                    else:
                        # Trim/pad to match lengths
                        min_len = min(mixed.shape[0], data.shape[0])
                        mixed = mixed[:min_len] + data[:min_len] * gain

                if mixed is None:
                    self.after(0, self.log, "No stems to play.")
                    self.after(0, self._stem_stop_done)
                    return

                # Play first 15 seconds as preview
                play_len = min(mixed.shape[0], int(15 * sr))
                sd.play(mixed[:play_len], samplerate=sr)

                # Wait for playback to finish or stop signal
                import threading as _th
                self._preview_thread = _th.current_thread()
                sd.wait()
            except Exception as e:
                self.after(0, self.log, f"Preview error: {e}")
            finally:
                self.after(0, self._stem_stop_done)

        threading.Thread(target=_play, daemon=True).start()

    def _stem_stop(self) -> None:
        """Stop current preview playback."""
        sd.stop()
        self._stem_stop_done()

    def _stem_stop_done(self) -> None:
        self._is_playing = False
        self._btn_preview.configure(state="normal")
        self._btn_stop.configure(state="disabled")

    def _stem_export(self) -> None:
        """Mix all stems at current levels and export to a single WAV file."""
        if not self._stem_mixer_output_dir:
            self.log("No stem data to export.")
            return

        from tkinter import filedialog as _fd
        out_path = _fd.asksaveasfilename(
            title="Export mixed stems",
            defaultextension=".wav",
            filetypes=[("WAV", "*.wav"), ("FLAC", "*.flac"), ("MP3", "*.mp3")],
            initialdir=self._stem_mixer_output_dir,
        )
        if not out_path:
            return

        def _do_export():
            try:
                master_gain = self._stem_master_vol.get() / 100.0
                mixed = None
                sr = None
                for key, info in self._stem_sliders.items():
                    gain = info["var"].get() / 100.0 * master_gain
                    if gain < 0.01:
                        continue
                    data, file_sr = sf.read(info["path"], dtype="float32")
                    if sr is None:
                        sr = file_sr
                    if data.ndim == 1:
                        data = data.reshape(-1, 1)
                    if mixed is None:
                        mixed = data * gain
                    else:
                        min_len = min(mixed.shape[0], data.shape[0])
                        mixed = mixed[:min_len] + data[:min_len] * gain

                if mixed is None:
                    self.after(0, self.log, "No stems to export.")
                    return

                sf.write(out_path, mixed, sr)
                self.after(0, self.log, f"Mixed stems exported: {out_path}")
                # Reveal in explorer
                self.after(100, lambda: self._reveal_folder(out_path))
            except Exception as e:
                self.after(0, self.log, f"Export error: {e}")

        threading.Thread(target=_do_export, daemon=True).start()

    def _stem_midi_all(self) -> None:
        """Extract MIDI from all melodic stems at once."""
        if not self._stem_sliders:
            self.log("No stems loaded.")
            return
        count = 0
        for key, info in self._stem_sliders.items():
            if key in ("vocals", "guitar", "piano", "bass"):
                self._stem_to_midi(info["path"], info["name"])
                count += 1
        if count:
            self.log(f"Scheduled MIDI extraction for {count} stem(s).")
        else:
            self.log("No melodic stems found.")

    def _stem_export_separate(self) -> None:
        """Export each stem at its current slider level as a separate WAV file."""
        if not self._stem_mixer_output_dir:
            self.log("No stem data to export.")
            return
        from tkinter import filedialog as _fd
        out_dir = _fd.askdirectory(
            title="Export all stems (custom levels) to folder",
            initialdir=self._stem_mixer_output_dir,
        )
        if not out_dir:
            return

        def _do_export_sep():
            try:
                master_gain = self._stem_master_vol.get() / 100.0
                exported = 0
                for key, info in self._stem_sliders.items():
                    gain = info["var"].get() / 100.0 * master_gain
                    data, sr = sf.read(info["path"], dtype="float32")
                    if gain != 1.0:
                        data = data * gain
                    stem_name = os.path.splitext(os.path.basename(info["path"]))[0]
                    out_path = os.path.join(out_dir, f"{stem_name}_custom.wav")
                    sf.write(out_path, data, sr)
                    exported += 1
                self.after(0, self.log, f"Exported {exported} stem(s) to: {out_dir}")
                self.after(100, lambda: self._reveal_folder(out_dir))
            except Exception as e:
                self.after(0, self.log, f"Export error: {e}")

        threading.Thread(target=_do_export_sep, daemon=True).start()

    def _stem_to_midi(self, stem_path: str, stem_label: str) -> None:
        """Extract MIDI from a melodic stem using librosa pitch tracking."""
        out_dir = self._stem_mixer_output_dir or os.path.dirname(stem_path)
        base = os.path.splitext(os.path.basename(stem_path))[0]
        midi_path = os.path.join(out_dir, f"{base}.mid")

        def _do_extract():
            try:
                self.after(0, self.log, f"Extracting MIDI from {stem_label}...")
                y, sr = sf.read(stem_path, dtype="float32")
                if y.ndim == 2:
                    y = y.mean(axis=1)

                # Pitch tracking with librosa
                fmin, fmax = librosa.note_to_hz("C2"), librosa.note_to_hz("C7")
                f0, voiced, _ = librosa.pyin(y, fmin=fmin, fmax=fmax, sr=sr)
                times = librosa.times_like(f0, sr=sr)

                # Onset detection for note segmentation
                onset_frames = librosa.onset.onset_detect(y=y, sr=sr, backtrack=True)
                onset_times = librosa.frames_to_time(onset_frames, sr=sr)

                # Group pitches into notes bounded by onsets
                notes = []
                onset_idx = 0
                min_note_dur = 0.05  # 50ms minimum note length

                for i in range(len(onset_times)):
                    t_start = onset_times[i]
                    t_end = onset_times[i + 1] if i + 1 < len(onset_times) else times[-1]
                    if t_end - t_start < min_note_dur:
                        continue
                    # Average pitch in this segment
                    mask = (times >= t_start) & (times < t_end) & voiced
                    if not mask.any():
                        continue
                    freq = f0[mask]
                    if len(freq) == 0:
                        continue
                    pitch_hz = np.median(freq)
                    midi_note = int(round(12 * np.log2(pitch_hz / 440.0) + 69))
                    midi_note = max(0, min(127, midi_note))
                    velocity = min(100, int(np.median(voiced[mask]) * 80 + 20))
                    notes.append((midi_note, t_start, t_end, velocity))

                if not notes:
                    self.after(0, self.log, f"No notes detected in {stem_label}.")
                    return

                self._write_midi(notes, midi_path)
                self.after(0, self.log, f"MIDI saved: {midi_path} ({len(notes)} notes)")
                self.after(100, lambda: self._reveal_folder(midi_path))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, self.log, f"MIDI extraction error: {e}")

        threading.Thread(target=_do_extract, daemon=True).start()

    @staticmethod
    def _write_midi(notes, output_path, tempo=120):
        """Write a simple single-track MIDI file from (pitch, start, end, velocity) tuples."""
        def _write_vlq(buf, value):
            """Write a variable-length quantity to buffer."""
            v = value
            bytes_arr = []
            bytes_arr.append(v & 0x7F)
            while v > 0x7F:
                v >>= 7
                bytes_arr.append((v & 0x7F) | 0x80)
            for b in reversed(bytes_arr):
                buf.append(b)

        ticks_per_beat = 480
        microsec_per_beat = 60_000_000 // tempo

        all_notes = []
        for pitch, start, end, vel in notes:
            start_tick = int(start * tempo * ticks_per_beat / 60)
            end_tick = int(end * tempo * ticks_per_beat / 60)
            if end_tick <= start_tick:
                end_tick = start_tick + ticks_per_beat // 8
            all_notes.append((pitch, start_tick, end_tick, vel))

        if not all_notes:
            return

        max_tick = max(n[2] for n in all_notes)

        data = bytearray()
        data.extend(b"MThd")
        data.extend((0, 0, 0, 6))
        data.extend((0, 1))
        data.extend((0, 2))
        data.extend((ticks_per_beat >> 8, ticks_per_beat & 0xFF))

        data.extend(b"MTrk")
        track0 = bytearray()
        track0.extend((0, 0xFF, 0x51, 3))
        track0.extend((microsec_per_beat >> 16, (microsec_per_beat >> 8) & 0xFF, microsec_per_beat & 0xFF))
        track0.extend((0, 0xFF, 0x2F, 0))
        data.extend((len(track0) >> 24, (len(track0) >> 16) & 0xFF,
                      (len(track0) >> 8) & 0xFF, len(track0) & 0xFF))
        data.extend(track0)

        data.extend(b"MTrk")
        track1 = bytearray()
        all_notes.sort(key=lambda n: n[1])

        current_time = 0
        for pitch, start_tick, end_tick, vel in all_notes:
            delta = start_tick - current_time
            _write_vlq(track1, delta)
            track1.extend((0x90, pitch, vel))
            delta = end_tick - start_tick
            _write_vlq(track1, delta)
            track1.extend((0x80, pitch, 0))
            current_time = end_tick

        _write_vlq(track1, max(0, max_tick - current_time))
        track1.extend((0xFF, 0x2F, 0))
        data.extend((len(track1) >> 24, (len(track1) >> 16) & 0xFF,
                      (len(track1) >> 8) & 0xFF, len(track1) & 0xFF))
        data.extend(track1)

        with open(output_path, "wb") as f:
            f.write(data)

