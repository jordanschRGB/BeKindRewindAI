"""Tests for engine.errors module."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.errors import (
    ERROR_CODES,
    get_error,
    get_error_dict,
    format_error_message,
    check_error_for_guidance,
    ErrorCode,
)


def test_error_codes_exist():
    assert len(ERROR_CODES) > 0
    assert "NO_SESSION" in ERROR_CODES
    assert "FFMPEG_NOT_FOUND" in ERROR_CODES
    assert "DEVICE_NOT_FOUND" in ERROR_CODES


def test_get_error_returns_error_code():
    error = get_error("NO_SESSION")
    assert isinstance(error, ErrorCode)
    assert error.code == "NO_SESSION"


def test_get_error_unknown_returns_generic():
    error = get_error("UNKNOWN_CODE")
    assert isinstance(error, ErrorCode)
    assert error.code == "UNKNOWN_CODE"


def test_get_error_dict():
    result = get_error_dict("NO_SESSION")
    assert isinstance(result, dict)
    assert "error" in result
    assert "code" in result
    assert result["code"] == "NO_SESSION"


def test_get_error_dict_with_guidance():
    result = get_error_dict("CAPTURE_FAILED")
    assert isinstance(result, dict)
    assert "guidance" in result


def test_format_error_message():
    msg = format_error_message("NO_SESSION")
    assert isinstance(msg, str)
    assert "session" in msg.lower()


def test_check_error_for_guidance_returns_hint():
    hint = check_error_for_guidance("Device not found in /dev/video0")
    assert hint is not None


def test_check_error_for_guidance_returns_none():
    hint = check_error_for_guidance("Something went wrong")
    assert hint is None
