"""Tests for tape library."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from library import list_tapes, get_tape, save_metadata


def test_list_tapes_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        tapes = list_tapes(d)
        assert tapes == []


def test_save_and_list_tape():
    with tempfile.TemporaryDirectory() as d:
        meta = {
            "filename": "Tape_001_2026-03-25.mp4",
            "duration_seconds": 2847,
            "size_bytes": 1073741824,
            "validation": {"has_audio": True, "has_video": True},
        }
        mp4_path = os.path.join(d, "Tape_001_2026-03-25.mp4")
        with open(mp4_path, "w") as f:
            f.write("fake")
        save_metadata(d, "Tape_001_2026-03-25", meta)
        tapes = list_tapes(d)
        assert len(tapes) == 1
        assert tapes[0]["filename"] == "Tape_001_2026-03-25.mp4"


def test_get_tape_by_name():
    with tempfile.TemporaryDirectory() as d:
        meta = {"filename": "Tape_001.mp4", "duration_seconds": 100}
        save_metadata(d, "Tape_001", meta)
        tape = get_tape(d, "Tape_001")
        assert tape is not None
        assert tape["duration_seconds"] == 100


def test_get_tape_not_found():
    with tempfile.TemporaryDirectory() as d:
        tape = get_tape(d, "nonexistent")
        assert tape is None
