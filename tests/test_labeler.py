"""Tests for smart labeling."""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.labeler import generate_labels, _parse_labels, sample_frames


def test_parse_labels_valid_json():
    text = '{"title": "Christmas 1995", "description": "Kids opening presents", "tags": ["family", "christmas"]}'
    result = _parse_labels(text)
    assert result is not None
    assert result["title"] == "Christmas 1995"
    assert "family" in result["tags"]


def test_parse_labels_with_markdown():
    text = '```json\n{"title": "Test", "description": "Desc", "tags": ["a"]}\n```'
    result = _parse_labels(text)
    assert result is not None
    assert result["title"] == "Test"


def test_parse_labels_embedded_json():
    text = 'Here is the result: {"title": "Birthday", "description": "Party", "tags": ["fun"]} done.'
    result = _parse_labels(text)
    assert result is not None
    assert result["title"] == "Birthday"


def test_parse_labels_invalid():
    result = _parse_labels("this is not json at all")
    assert result is None


def test_generate_labels_no_input():
    success, labels, err = generate_labels()
    assert success is False
    assert "need at least" in err.lower()


def test_generate_labels_no_backend():
    """With no API, no NPU, and no local model, should fail gracefully."""
    with patch("engine.labeler.get_api_url", return_value=None):
        with patch("engine.labeler._check_npu_available", return_value=False):
            with patch("engine.labeler._call_local", return_value=(False, None, "No model available")):
                success, labels, err = generate_labels(transcript="hello world")
                assert success is False


def test_sample_frames_missing_video():
    success, frames, err = sample_frames("/nonexistent/video.mp4")
    assert success is False
    assert "not found" in err.lower()
