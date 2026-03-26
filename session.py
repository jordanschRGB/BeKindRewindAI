"""Batch session manager — tracks state across multiple tape captures."""

import enum
import time


class SessionState(enum.Enum):
    WAITING = "waiting"
    RECORDING = "recording"
    ENCODING = "encoding"
    VALIDATING = "validating"
    DONE = "done"
    ERROR = "error"


class Session:
    def __init__(self, tape_count, output_dir, names=None):
        self.tape_count = tape_count
        self.output_dir = output_dir
        self.names = names or []
        self.current_tape = 0
        self.state = SessionState.WAITING
        self.tapes = []
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.error = None

    def advance(self):
        self.current_tape += 1
        self.state = SessionState.RECORDING
        tape_name = ""
        if self.names and self.current_tape <= len(self.names):
            tape_name = self.names[self.current_tape - 1]
        self.tapes.append({
            "number": self.current_tape,
            "name": tape_name,
            "status": "recording",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "file": None,
            "validation": None,
        })

    def complete_tape(self, validation_result, file_path=None):
        if self.tapes:
            tape = self.tapes[-1]
            tape["status"] = "done" if validation_result.get("valid") else "failed"
            tape["validation"] = validation_result
            tape["file"] = file_path
            tape["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        if self.current_tape >= self.tape_count:
            self.state = SessionState.DONE
        else:
            self.state = SessionState.WAITING

    def set_state(self, state):
        self.state = state

    def set_error(self, msg):
        self.state = SessionState.ERROR
        self.error = msg

    def to_dict(self):
        return {
            "tape_count": self.tape_count,
            "current_tape": self.current_tape,
            "state": self.state.value,
            "tapes": self.tapes,
            "created_at": self.created_at,
            "error": self.error,
        }
