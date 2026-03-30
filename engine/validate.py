"""Post-capture file validation using ffprobe."""

import json
import os
import subprocess

MIN_DURATION_SECONDS = 10


def probe_file(path):
    """Run ffprobe and return parsed JSON output."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return None


def validate_capture(path):
    """Validate a captured file. Returns dict with valid, error, duration_seconds, size_bytes, has_audio, has_video."""
    result = {
        "valid": False,
        "error": None,
        "duration_seconds": 0,
        "size_bytes": 0,
        "has_audio": False,
        "has_video": False,
    }

    if not os.path.exists(path):
        result["error"] = "File not found"
        return result

    size = os.path.getsize(path)
    result["size_bytes"] = size
    if size == 0:
        result["error"] = "File is empty (0 bytes)"
        return result

    probe = probe_file(path)
    if probe is None:
        result["error"] = "Could not read file metadata"
        return result

    duration_str = probe.get("format", {}).get("duration")
    duration = float(duration_str) if duration_str else 0.0
    result["duration_seconds"] = int(duration)

    streams = probe.get("streams", [])
    result["has_video"] = any(s["codec_type"] == "video" for s in streams)
    result["has_audio"] = any(s["codec_type"] == "audio" for s in streams)

    if duration < MIN_DURATION_SECONDS:
        result["error"] = f"Recording too short ({int(duration)}s). Minimum is {MIN_DURATION_SECONDS}s."
        return result

    result["valid"] = True
    return result
