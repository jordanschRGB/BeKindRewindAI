"""
memoryvault.engine.devices
Device detection for VHS capture cards and audio inputs.
Supports Linux (v4l2/ALSA/PulseAudio), macOS (avfoundation), Windows (dshow).
"""

import os
import platform
import re
import subprocess
import tempfile

SYSTEM = platform.system()  # "Linux", "Darwin", "Windows"


def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available on PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Video Detection ───────────────────────────────────────────────────────────

def _detect_video_linux():
    """Scan /dev/video* and probe each with ffmpeg."""
    import glob
    devices = sorted(glob.glob("/dev/video*"))
    results = []
    for dev in devices:
        num = dev.replace("/dev/video", "")
        name_path = f"/sys/class/video4linux/video{num}/name"
        label = dev
        if os.path.exists(name_path):
            try:
                with open(name_path) as f:
                    label = f"{f.read().strip()} ({dev})"
            except OSError:
                pass
        try:
            probe = subprocess.run(
                ["ffmpeg", "-f", "v4l2", "-i", dev, "-t", "0.1", "-f", "null", "-"],
                capture_output=True, text=True, timeout=5,
            )
            if "Invalid" not in probe.stderr:
                results.append((label, {"format": "v4l2", "device": dev}))
        except (subprocess.TimeoutExpired, OSError):
            pass
    return results


def _detect_video_mac():
    """Use avfoundation to list video devices on macOS."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    results = []
    in_video = False
    for line in result.stderr.splitlines():
        if "AVFoundation video devices:" in line:
            in_video = True
            continue
        if "AVFoundation audio devices:" in line:
            break
        if in_video:
            m = re.search(r"\[(\d+)\]\s+(.+)", line)
            if m:
                idx, name = m.group(1), m.group(2).strip()
                results.append((name, {"format": "avfoundation", "device": idx}))
    return results


def _detect_video_windows():
    """Use dshow to list video devices on Windows."""
    results = []
    for name in _dshow_list_devices("video"):
        results.append((name, {"format": "dshow", "device": f"video={name}"}))
    return results


def _dshow_list_devices(device_type="video"):
    """Parse ffmpeg dshow output. Each line has "(video)", "(audio)", or "(none)" tag.

    Args:
        device_type: "video" or "audio"

    Returns:
        list of device name strings matching the requested type.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "dshow", "-list_devices", "true", "-i", "dummy"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    names = []
    for line in result.stderr.splitlines():
        if "Alternative name" in line:
            continue
        # Match: "Device Name" (video) or "Device Name" (audio)
        m = re.search(r'"(.+?)"\s+\((' + device_type + r')\)', line)
        if m:
            names.append(m.group(1))
    return names


def detect_video_devices():
    """
    Detect available video capture devices.

    Returns:
        list of (label: str, config_dict: dict) tuples.
        config_dict contains 'format' and 'device' keys suitable for ffmpeg.
    """
    if SYSTEM == "Linux":
        return _detect_video_linux()
    elif SYSTEM == "Darwin":
        return _detect_video_mac()
    elif SYSTEM == "Windows":
        return _detect_video_windows()
    return []


# ── Audio Detection ───────────────────────────────────────────────────────────

def _detect_audio_linux():
    """List ALSA / PulseAudio capture sources."""
    results = []
    # Try PulseAudio default first
    try:
        subprocess.run(
            ["ffmpeg", "-f", "pulse", "-i", "default", "-t", "0.1", "-f", "null", "-"],
            capture_output=True, text=True, timeout=5,
        )
        results.append(("Default audio input (PulseAudio)", {"format": "pulse", "device": "default"}))
    except (subprocess.TimeoutExpired, OSError):
        pass

    # ALSA hw devices via arecord
    try:
        arecord = subprocess.run(
            ["arecord", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        for line in arecord.stdout.splitlines():
            m = re.match(r"card (\d+):.*\[(.+?)\].*device (\d+):.*\[(.+?)\]", line)
            if m:
                card, card_name, dev, dev_name = m.groups()
                label = f"{card_name} - {dev_name}"
                hw = f"hw:{card},{dev}"
                results.append((label, {"format": "alsa", "device": hw}))
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not results:
        results.append(("Default audio input", {"format": "alsa", "device": "default"}))
    return results


def _detect_audio_mac():
    """Use avfoundation to list audio devices on macOS."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []

    results = []
    in_audio = False
    for line in result.stderr.splitlines():
        if "AVFoundation audio devices:" in line:
            in_audio = True
            continue
        if in_audio:
            m = re.search(r"\[(\d+)\]\s+(.+)", line)
            if m:
                idx, name = m.group(1), m.group(2).strip()
                results.append((name, {"format": "avfoundation", "device": idx}))
    return results


def _detect_audio_windows():
    """Use dshow to list audio devices on Windows."""
    results = []
    for name in _dshow_list_devices("audio"):
        results.append((name, {"format": "dshow", "device": f"audio={name}"}))
    return results


def detect_audio_devices():
    """
    Detect available audio input devices.

    Returns:
        list of (label: str, config_dict: dict) tuples.
        config_dict contains 'format' and 'device' keys suitable for ffmpeg.
    """
    if SYSTEM == "Linux":
        return _detect_audio_linux()
    elif SYSTEM == "Darwin":
        return _detect_audio_mac()
    elif SYSTEM == "Windows":
        return _detect_audio_windows()
    return []


# ── Test Capture ──────────────────────────────────────────────────────────────

def test_capture(video_cfg: dict, audio_cfg: dict) -> tuple:
    """
    Run a 3-second test capture to verify the selected devices work together.

    Args:
        video_cfg: dict with 'format' and 'device' keys.
        audio_cfg: dict with 'format' and 'device' keys.

    Returns:
        (success: bool, error_msg: str | None)
        error_msg is None on success, a human-readable string on failure.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".mkv", delete=False)
    tmp.close()

    cmd = ["ffmpeg", "-y"]

    if SYSTEM == "Linux":
        cmd += ["-f", video_cfg["format"], "-i", video_cfg["device"]]
        cmd += ["-f", audio_cfg["format"], "-i", audio_cfg["device"]]
    elif SYSTEM == "Darwin":
        av_input = f"{video_cfg['device']}:{audio_cfg['device']}"
        cmd += ["-f", "avfoundation", "-i", av_input]
    elif SYSTEM == "Windows":
        combined = f"{video_cfg['device']}:{audio_cfg['device']}"
        cmd += ["-f", "dshow", "-i", combined]

    cmd += ["-t", "3", "-c:v", "rawvideo", "-c:a", "pcm_s16le", tmp.name]

    result = None
    file_ok = False
    error_msg = None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        file_ok = os.path.exists(tmp.name) and os.path.getsize(tmp.name) > 0
    except subprocess.TimeoutExpired:
        error_msg = "Test capture timed out after 15 seconds"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    if file_ok:
        return True, None

    if error_msg is None:
        # Build error from ffmpeg stderr if available
        if result and result.stderr:
            last_lines = result.stderr.strip().splitlines()[-3:]
            error_msg = "Test capture failed: " + " | ".join(last_lines)
        else:
            error_msg = "Test capture failed: output file was empty or missing"

    return False, error_msg
