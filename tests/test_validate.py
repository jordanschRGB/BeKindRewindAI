"""Tests for post-capture file validation."""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.validate import validate_capture


def test_validate_missing_file():
    result = validate_capture("/nonexistent/file.mkv")
    assert result["valid"] is False
    assert "not found" in result["error"].lower()


def test_validate_empty_file():
    with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as f:
        path = f.name
    try:
        result = validate_capture(path)
        assert result["valid"] is False
        assert "empty" in result["error"].lower()
    finally:
        os.unlink(path)


def test_validate_too_short():
    probe_data = {
        "format": {"duration": "5.0", "size": "50000"},
        "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
    }
    with patch("engine.validate.probe_file", return_value=probe_data), \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=50000):
        result = validate_capture("/fake/file.mkv")
        assert result["valid"] is False
        assert "short" in result["error"].lower()


def test_validate_no_audio():
    probe_data = {
        "format": {"duration": "300.0", "size": "500000"},
        "streams": [{"codec_type": "video"}],
    }
    with patch("engine.validate.probe_file", return_value=probe_data), \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=500000):
        result = validate_capture("/fake/file.mkv")
        assert result["valid"] is True
        assert result["has_audio"] is False


def test_validate_good_file():
    probe_data = {
        "format": {"duration": "2847.0", "size": "1073741824"},
        "streams": [{"codec_type": "video"}, {"codec_type": "audio"}],
    }
    with patch("engine.validate.probe_file", return_value=probe_data), \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=1073741824):
        result = validate_capture("/fake/file.mkv")
        assert result["valid"] is True
        assert result["has_audio"] is True
        assert result["has_video"] is True
        assert result["duration_seconds"] == 2847
