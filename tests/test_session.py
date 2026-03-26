"""Tests for batch session manager."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session import Session, SessionState


def test_session_creation():
    s = Session(tape_count=3, output_dir="/tmp/test")
    assert s.tape_count == 3
    assert s.current_tape == 0
    assert s.state == SessionState.WAITING


def test_session_advance():
    s = Session(tape_count=3, output_dir="/tmp/test")
    s.state = SessionState.WAITING
    s.advance()
    assert s.current_tape == 1
    assert s.state == SessionState.RECORDING


def test_session_complete_tape():
    s = Session(tape_count=2, output_dir="/tmp/test")
    s.advance()
    s.complete_tape({"valid": True, "duration_seconds": 300})
    assert s.tapes[0]["status"] == "done"
    assert s.state == SessionState.WAITING


def test_session_all_done():
    s = Session(tape_count=1, output_dir="/tmp/test")
    s.advance()
    s.complete_tape({"valid": True, "duration_seconds": 300})
    assert s.state == SessionState.DONE


def test_session_status_dict():
    s = Session(tape_count=2, output_dir="/tmp/test")
    d = s.to_dict()
    assert d["tape_count"] == 2
    assert d["current_tape"] == 0
    assert d["state"] == "waiting"
    assert len(d["tapes"]) == 0
