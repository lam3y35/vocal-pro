"""Tests for the _write_midi helper function in api_server/main.py."""

from __future__ import annotations

import os
import tempfile


def _import_midi_writer():
    """Import the _write_midi function from the api_server module."""
    from api_server.main import _write_midi
    return _write_midi


class TestMidiWrite:
    def test_write_midi_creates_file(self):
        write = _import_midi_writer()
        notes = [
            {"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80},
            {"pitch": 64, "start": 0.5, "end": 1.0, "velocity": 75},
            {"pitch": 67, "start": 1.0, "end": 1.5, "velocity": 90},
        ]
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write(notes, fname)
            assert os.path.isfile(fname)
            assert os.path.getsize(fname) > 20  # MIDI header + data
        finally:
            os.unlink(fname)

    def test_write_midi_mthd_header(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname)
            with open(fname, "rb") as fh:
                header = fh.read(4)
                assert header == b"MThd"
        finally:
            os.unlink(fname)

    def test_write_midi_mtrk_markers(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                assert data.count(b"MTrk") == 2  # tempo track + note track
        finally:
            os.unlink(fname)

    def test_write_midi_end_of_track(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                assert data[-3:] == b"\xff\x2f\x00"  # End of Track
        finally:
            os.unlink(fname)

    def test_write_midi_empty_notes_no_file(self):
        """If no notes, file should not be created."""
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        os.unlink(fname)  # Delete so we can test non-creation
        write([], fname)
        assert not os.path.isfile(fname)

    def test_write_midi_single_note(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                # Note On: 0x90, pitch, velocity
                assert b"\x90" in data
                assert bytes([60]) in data  # pitch
        finally:
            os.unlink(fname)

    def test_write_midi_note_off(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                # Note Off: 0x80, pitch, 0
                assert b"\x80" in data
                assert bytes([60]) in data
        finally:
            os.unlink(fname)

    def test_write_midi_pitch_range(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            notes = [
                {"pitch": 0, "start": 0.0, "end": 0.5, "velocity": 80},   # C-1
                {"pitch": 127, "start": 0.5, "end": 1.0, "velocity": 80},  # G9
            ]
            write(notes, fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                assert bytes([0]) in data  # pitch 0
                assert bytes([127]) in data  # pitch 127
        finally:
            os.unlink(fname)

    def test_write_midi_velocity_values(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            notes = [
                {"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 100},
                {"pitch": 64, "start": 0.5, "end": 1.0, "velocity": 50},
            ]
            write(notes, fname)
            with open(fname, "rb") as fh:
                data = fh.read()
                assert bytes([100]) in data
                assert bytes([50]) in data
        finally:
            os.unlink(fname)

    def test_write_midi_tempo_marker(self):
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname, tempo=120)
            with open(fname, "rb") as fh:
                data = fh.read()
                # Tempo meta event: 0xFF 0x51 0x03
                assert b"\xff\x51\x03" in data
        finally:
            os.unlink(fname)

    def test_write_midi_different_tempos(self):
        write = _import_midi_writer()
        for tempo in [60, 120, 200]:
            with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
                fname = f.name
            try:
                write([{"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80}], fname, tempo=tempo)
                assert os.path.getsize(fname) > 20
            finally:
                os.unlink(fname)

    def test_write_midi_back_to_back_notes(self):
        """Test notes with no gap between them (end=start of next)."""
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            notes = [
                {"pitch": 60, "start": 0.0, "end": 0.5, "velocity": 80},
                {"pitch": 62, "start": 0.5, "end": 1.0, "velocity": 80},
                {"pitch": 64, "start": 1.0, "end": 1.5, "velocity": 80},
            ]
            write(notes, fname)
            assert os.path.getsize(fname) > 20
        finally:
            os.unlink(fname)

    def test_write_midi_negative_duration_clamped(self):
        """If end <= start, the MIDI writer uses a minimum duration."""
        write = _import_midi_writer()
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            fname = f.name
        try:
            notes = [
                {"pitch": 60, "start": 0.5, "end": 0.1, "velocity": 80},  # bad duration
            ]
            write(notes, fname)
            assert os.path.getsize(fname) > 20
        finally:
            os.unlink(fname)
