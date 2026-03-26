"""
memoryvault.engine.capture
Recording logic: signal detection, Recorder class, ffmpeg command builder.
"""

import os
import platform
import re
import subprocess
import tempfile
import threading
import time

SYSTEM = platform.system()


# ── Command Builder ───────────────────────────────────────────────────────────

def _build_capture_cmd(
    video_cfg: dict,
    audio_cfg: dict,
    output_path: str,
    duration: int | None = None,
) -> list:
    """
    Build the ffmpeg command for capturing raw video.

    Includes blackdetect and silencedetect filters so the Recorder's auto-stop
    monitor can parse ffmpeg stderr for end-of-tape detection.

    Args:
        video_cfg: dict with 'format' and 'device' keys.
        audio_cfg: dict with 'format' and 'device' keys.
        output_path: Destination file path.
        duration: Optional recording limit in seconds.

    Returns:
        list of command tokens ready for subprocess.
    """
    cmd = ["ffmpeg", "-y"]

    if SYSTEM == "Linux":
        cmd += ["-f", video_cfg["format"]]
        cmd += ["-thread_queue_size", "1024"]
        cmd += ["-i", video_cfg["device"]]
        cmd += ["-f", audio_cfg["format"]]
        cmd += ["-thread_queue_size", "1024"]
        cmd += ["-i", audio_cfg["device"]]
    elif SYSTEM == "Darwin":
        av_input = f"{video_cfg['device']}:{audio_cfg['device']}"
        cmd += ["-f", "avfoundation", "-i", av_input]
    elif SYSTEM == "Windows":
        combined = f"{video_cfg['device']}:{audio_cfg['device']}"
        cmd += ["-f", "dshow", "-i", combined]

    if duration is not None:
        cmd += ["-t", str(duration)]

    # Detection filters — results appear in ffmpeg stderr
    vf = "blackdetect=d=5:pix_th=0.10"
    af = "silencedetect=n=-50dB:d=10"

    cmd += [
        "-vf", vf,
        "-af", af,
        "-c:v", "ffv1",        # Lossless video, good compression
        "-level", "3",          # FFV1 level 3 (multithreaded)
        "-c:a", "pcm_s16le",   # Uncompressed audio
        output_path,
    ]

    return cmd


# ── Signal Check ──────────────────────────────────────────────────────────────

def check_video_signal(video_cfg: dict, audio_cfg: dict) -> bool:
    """
    Sample 3 seconds to detect whether there is an actual video signal.

    Args:
        video_cfg: dict with 'format' and 'device' keys.
        audio_cfg: dict with 'format' and 'device' keys.

    Returns:
        True if a signal appears to be present, False if blank/missing.
        Returns True on timeout (assume OK; real capture will reveal issues).
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mkv", delete=False)
    tmp.close()

    cmd = _build_capture_cmd(video_cfg, audio_cfg, tmp.name, duration=3)

    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        return True  # Timeout treated as signal-present

    file_size = 0
    try:
        file_size = os.path.getsize(tmp.name)
    except OSError:
        pass

    try:
        os.unlink(tmp.name)
    except OSError:
        pass

    # Empty or tiny file means no real signal
    return file_size >= 1000


# ── Recorder ─────────────────────────────────────────────────────────────────

class Recorder:
    """
    Manages an ffmpeg recording process with auto-stop monitoring.

    Auto-stop triggers:
      - 10+ seconds of silence (silencedetect filter output)
      - 5+ seconds of black screen (blackdetect filter output)

    Usage:
        cmd = _build_capture_cmd(video_cfg, audio_cfg, "/path/to/output.mkv")
        rec = Recorder(cmd, "/path/to/output.mkv")
        rec.start()
        # ... poll rec.is_running() or wait
        rec.stop()
        print(rec.stop_reason)   # "silence" | "black_screen" | "user" | ""
    """

    def __init__(self, cmd: list, raw_path: str):
        self.cmd = cmd
        self.raw_path = raw_path
        self.process = None
        self.start_time = None
        self.stopped = False
        self.stop_reason = ""
        self._monitor_thread = None

    def start(self):
        """Launch ffmpeg and begin auto-stop monitoring in a background thread."""
        self.start_time = time.time()
        self.process = subprocess.Popen(
            self.cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._monitor_thread = threading.Thread(
            target=self._monitor_auto_stop, daemon=True
        )
        self._monitor_thread.start()

    def _monitor_auto_stop(self):
        """
        Read ffmpeg stderr line-by-line, triggering stop on:
          - silence_duration >= 10.0 seconds
          - black_duration >= 5.0 seconds
        """
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stderr.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace")

                # Silence detection
                m = re.search(r"silence_end:\s*([\d.]+).*silence_duration:\s*([\d.]+)", line)
                if m:
                    duration = float(m.group(2))
                    if duration >= 10.0:
                        self.stop_reason = "silence"
                        self.stop()
                        return

                # Black screen detection
                m = re.search(r"black_end:\s*([\d.]+).*black_duration:\s*([\d.]+)", line)
                if m:
                    duration = float(m.group(2))
                    if duration >= 5.0:
                        self.stop_reason = "black_screen"
                        self.stop()
                        return

            except Exception:
                break

    def stop(self):
        """Gracefully stop recording by sending 'q' to ffmpeg stdin."""
        if self.stopped:
            return
        self.stopped = True
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(b"q")
                self.process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.terminate()

    def elapsed(self) -> float:
        """Return seconds elapsed since start(), or 0 if not started."""
        if self.start_time:
            return time.time() - self.start_time
        return 0.0

    def is_running(self) -> bool:
        """Return True if the ffmpeg process is still active."""
        return self.process is not None and self.process.poll() is None
