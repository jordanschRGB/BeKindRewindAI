"""Tests for engine.doctor module."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.doctor import (
    run_diagnostics,
    check_ffmpeg,
    check_disk,
    check_config,
    check_dependencies,
)


def test_run_diagnostics_returns_dict():
    results = run_diagnostics()
    assert isinstance(results, dict)
    assert "checks" in results
    assert "all_passed" in results
    assert "platform" in results


def test_check_ffmpeg_returns_dict():
    result = check_ffmpeg()
    assert isinstance(result, dict)
    assert "name" in result
    assert "status" in result
    assert "details" in result
    assert result["name"] == "ffmpeg"


def test_check_disk_returns_dict():
    result = check_disk()
    assert isinstance(result, dict)
    assert "name" in result
    assert "status" in result
    assert "details" in result
    assert result["name"] == "disk_space"


def test_check_config_returns_dict():
    result = check_config()
    assert isinstance(result, dict)
    assert "name" in result
    assert "status" in result
    assert "details" in result
    assert result["name"] == "configuration"


def test_check_dependencies_returns_dict():
    result = check_dependencies()
    assert isinstance(result, dict)
    assert "name" in result
    assert "status" in result
    assert "details" in result
    assert result["name"] == "python_deps"
