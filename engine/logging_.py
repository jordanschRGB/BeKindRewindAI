"""Centralized logging configuration for MemoryVault.

Provides:
- Structured logging to both file (~/.memoryvault/logs/app.log) and stdout
- A VERBOSE flag that enables DEBUG-level logging when --verbose is passed
- Consistent log format with timestamps, levels, and source
"""

import logging
import os
import sys

LOG_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault", "logs")
LOG_FILE = os.path.join(LOG_DIR, "app.log")

VERBOSE = False
_loggers = {}
_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Get or create a logger with the given name.

    All loggers write to both ~/.memoryvault/logs/app.log and stdout.
    When VERBOSE=True, DEBUG level is enabled; otherwise INFO is the minimum.
    """
    if name in _loggers:
        return _loggers[name]

    _ensure_log_dir()

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if VERBOSE else logging.INFO)
    logger.handlers.clear()

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(_formatter)
    logger.addHandler(file_handler)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG if VERBOSE else logging.INFO)
    stdout_handler.setFormatter(_formatter)
    logger.addHandler(stdout_handler)

    _loggers[name] = logger
    return logger


def set_verbose(enabled: bool = True):
    """Enable or disable verbose (DEBUG-level) logging."""
    global VERBOSE
    VERBOSE = enabled
    for logger in _loggers.values():
        logger.setLevel(logging.DEBUG if enabled else logging.INFO)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG if enabled else logging.INFO)


class LogContext:
    """Context manager for temporary log level changes."""

    def __init__(self, logger: logging.Logger, level: int):
        self.logger = logger
        self.level = level
        self.old_level = None

    def __enter__(self):
        self.old_level = self.logger.level
        self.logger.setLevel(self.level)
        return self

    def __exit__(self, *args):
        self.logger.setLevel(self.old_level)


def log_error_with_guidance(logger: logging.Logger, error_msg: str, guidance_hints: dict):
    """Log an error message with structured guidance hints.

    Args:
        logger: The logger to use
        error_msg: The error message
        guidance_hints: Dict mapping error substrings to guidance strings.
                       If error_msg contains a key, the corresponding guidance is shown.
    """
    logger.error(error_msg)
    for hint_key, hint_text in guidance_hints.items():
        if hint_key in error_msg:
            logger.info(f"  Hint: {hint_text}")
            break
