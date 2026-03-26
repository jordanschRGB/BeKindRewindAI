"""Tests for audio transcription via faster-whisper."""

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.transcribe import extract_audio, transcribe_audio, transcribe_video, is_whisper_available


def test_extract_audio_missing_file():
    success, path, err = extract_audio("/nonexistent/video.mp4")
    assert success is False
    assert "not found" in err.lower()


def test_extract_audio_success():
    """Mock ffmpeg to simulate successful extraction."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        video_path = f.name
        f.write(b"fake video")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
        f.write(b"fake wav data")

    try:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("engine.transcribe.subprocess.run", return_value=mock_result):
            success, path, err = extract_audio(video_path, output_path=wav_path)
            assert success is True
            assert path == wav_path
    finally:
        for p in [video_path, wav_path]:
            try:
                os.unlink(p)
            except OSError:
                pass


def test_whisper_available():
    """faster-whisper should be installed."""
    assert is_whisper_available() is True


def test_transcribe_audio_no_whisper():
    """Should fail gracefully when faster-whisper isn't available."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"fake")
        wav_path = f.name

    try:
        with patch("engine.transcribe.is_whisper_available", return_value=False):
            success, transcript, err = transcribe_audio(wav_path)
            assert success is False
            assert "not installed" in err.lower()
    finally:
        os.unlink(wav_path)


def test_transcribe_video_missing():
    success, transcript, err = transcribe_video("/nonexistent/video.mp4")
    assert success is False
