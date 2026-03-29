"""Tests for storage cleanup module."""

import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cleanup import (
    get_storage_stats,
    cleanup_old_recordings,
    cleanup_orphaned_temp_files,
    set_tape_keep,
    get_tape_keep_status,
    _find_orphaned_frame_dirs,
)


def test_get_storage_stats_empty_dir():
    with tempfile.TemporaryDirectory() as d:
        stats = get_storage_stats(d)
        assert stats["tape_count"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["disk_free_gb"] > 0


def test_get_storage_stats_with_tapes():
    with tempfile.TemporaryDirectory() as d:
        meta = {
            "base_name": "TestTape_2026-03-25",
            "filename": "TestTape_2026-03-25.mp4",
            "duration_seconds": 100,
            "size_bytes": 1024,
            "captured_at": "2026-03-25T10:00:00",
        }
        with open(os.path.join(d, "TestTape_2026-03-25.json"), "w") as f:
            json.dump(meta, f)
        with open(os.path.join(d, "TestTape_2026-03-25.mp4"), "w") as f:
            f.write("x" * 1024)

        stats = get_storage_stats(d)
        assert stats["tape_count"] == 1
        assert stats["total_size_bytes"] >= 1024
        assert stats["oldest_tape"] == "2026-03-25T10:00:00"
        assert stats["newest_tape"] == "2026-03-25T10:00:00"


def test_cleanup_old_recordings_dry_run():
    with tempfile.TemporaryDirectory() as d:
        meta_old = {
            "base_name": "OldTape",
            "filename": "OldTape.mp4",
            "size_bytes": 100,
            "captured_at": "2020-01-01T00:00:00",
        }
        with open(os.path.join(d, "OldTape.json"), "w") as f:
            json.dump(meta_old, f)
        with open(os.path.join(d, "OldTape.mp4"), "w") as f:
            f.write("old")

        result = cleanup_old_recordings(d, days=30, dry_run=True)
        assert result["dry_run"] is True
        assert result["deleted_count"] == 1
        assert os.path.exists(os.path.join(d, "OldTape.json"))
        assert os.path.exists(os.path.join(d, "OldTape.mp4"))


def test_cleanup_old_recordings_actually_deletes():
    with tempfile.TemporaryDirectory() as d:
        meta_old = {
            "base_name": "OldTape",
            "filename": "OldTape.mp4",
            "size_bytes": 100,
            "captured_at": "2020-01-01T00:00:00",
        }
        with open(os.path.join(d, "OldTape.json"), "w") as f:
            json.dump(meta_old, f)
        with open(os.path.join(d, "OldTape.mp4"), "w") as f:
            f.write("old")

        result = cleanup_old_recordings(d, days=30, dry_run=False)
        assert result["deleted_count"] == 1
        assert not os.path.exists(os.path.join(d, "OldTape.json"))
        assert not os.path.exists(os.path.join(d, "OldTape.mp4"))


def test_cleanup_respects_keep_flag():
    with tempfile.TemporaryDirectory() as d:
        meta_protected = {
            "base_name": "ProtectedTape",
            "filename": "ProtectedTape.mp4",
            "size_bytes": 100,
            "captured_at": "2020-01-01T00:00:00",
            "keep": True,
        }
        with open(os.path.join(d, "ProtectedTape.json"), "w") as f:
            json.dump(meta_protected, f)
        with open(os.path.join(d, "ProtectedTape.mp4"), "w") as f:
            f.write("protected")

        result = cleanup_old_recordings(d, days=30, dry_run=False)
        assert result["deleted_count"] == 0
        assert "ProtectedTape" in result["protected_tapes"]
        assert os.path.exists(os.path.join(d, "ProtectedTape.json"))
        assert os.path.exists(os.path.join(d, "ProtectedTape.mp4"))


def test_cleanup_new_tapes_not_deleted():
    with tempfile.TemporaryDirectory() as d:
        meta_new = {
            "base_name": "NewTape",
            "filename": "NewTape.mp4",
            "size_bytes": 100,
            "captured_at": "2026-03-28T00:00:00",
        }
        with open(os.path.join(d, "NewTape.json"), "w") as f:
            json.dump(meta_new, f)
        with open(os.path.join(d, "NewTape.mp4"), "w") as f:
            f.write("new")

        result = cleanup_old_recordings(d, days=30, dry_run=False)
        assert result["deleted_count"] == 0
        assert os.path.exists(os.path.join(d, "NewTape.json"))


def test_set_tape_keep():
    with tempfile.TemporaryDirectory() as d:
        meta = {"base_name": "TestTape", "filename": "TestTape.mp4"}
        with open(os.path.join(d, "TestTape.json"), "w") as f:
            json.dump(meta, f)

        success, err = set_tape_keep(d, "TestTape", keep=True)
        assert success is True
        assert err is None

        with open(os.path.join(d, "TestTape.json")) as f:
            updated = json.load(f)
        assert updated["keep"] is True

        success, err = set_tape_keep(d, "TestTape", keep=False)
        assert success is True

        with open(os.path.join(d, "TestTape.json")) as f:
            updated = json.load(f)
        assert updated["keep"] is False


def test_set_tape_keep_not_found():
    with tempfile.TemporaryDirectory() as d:
        success, err = set_tape_keep(d, "Nonexistent", keep=True)
        assert success is False
        assert "not found" in err.lower()


def test_get_tape_keep_status():
    with tempfile.TemporaryDirectory() as d:
        meta = {"base_name": "TestTape", "keep": True}
        with open(os.path.join(d, "TestTape.json"), "w") as f:
            json.dump(meta, f)

        status = get_tape_keep_status(d, "TestTape")
        assert status is True

        status = get_tape_keep_status(d, "Nonexistent")
        assert status is None


def test_cleanup_orphaned_temp_files_dry_run():
    with tempfile.TemporaryDirectory() as d:
        temp_wav = os.path.join(d, "temp_12345.wav")
        with open(temp_wav, "w") as f:
            f.write("temp")

        old_mtime = time.time() - (2 * 86400)
        os.utime(temp_wav, (old_mtime, old_mtime))

        result = cleanup_orphaned_temp_files(d, dry_run=True)
        assert result["dry_run"] is True
        assert result["deleted_files"] == 1
        assert os.path.exists(temp_wav)


def test_cleanup_orphaned_temp_files_actually_deletes():
    with tempfile.TemporaryDirectory() as d:
        temp_wav = os.path.join(d, "temp_12345.wav")
        with open(temp_wav, "w") as f:
            f.write("temp")

        old_mtime = time.time() - (2 * 86400)
        os.utime(temp_wav, (old_mtime, old_mtime))

        result = cleanup_orphaned_temp_files(d, dry_run=False)
        assert result["deleted_files"] == 1
        assert not os.path.exists(temp_wav)


def test_find_orphaned_frame_dirs():
    import shutil
    import tempfile as tf
    tmp = tf.gettempdir()
    test_dir = os.path.join(tmp, "memoryvault_frames_test_12345")
    os.makedirs(test_dir, exist_ok=True)
    try:
        found = _find_orphaned_frame_dirs()
        assert any("memoryvault_frames_test_12345" in d for d in found)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)