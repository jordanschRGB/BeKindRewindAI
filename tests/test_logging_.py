"""Tests for engine.logging_ module."""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.logging_ import get_logger, set_verbose, LogContext


def test_get_logger_returns_logger():
    logger = get_logger("test_logger")
    assert logger is not None
    assert logger.name == "test_logger"


def test_get_logger_caches():
    logger1 = get_logger("test_cached")
    logger2 = get_logger("test_cached")
    assert logger1 is logger2


def test_set_verbose_changes_level():
    set_verbose(True)
    from engine import logging_ as log_module
    assert log_module.VERBOSE is True

    set_verbose(False)
    assert log_module.VERBOSE is False


def test_log_context_temporary_level():
    logger = get_logger("test_context")
    original_level = logger.level

    with LogContext(logger, 10):
        assert logger.level == 10

    assert logger.level == original_level
