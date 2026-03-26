"""
memoryvault.engine.encode
Encoding logic: convert raw FFV1/MKV captures to compressed MP4 using ffmpeg x264.
No HandBrake dependency.
"""

import os
import subprocess


def encode_to_mp4(
    raw_path: str,
    output_path: str,
    timeout: int = 7200,
) -> tuple:
    """
    Encode a raw capture file to MP4 using ffmpeg x264.

    Settings:
      - Video: x264, preset fast, crf 20
      - Audio: AAC 160k
      - No HandBrake dependency

    Args:
        raw_path: Path to the raw capture file (e.g., .mkv from Recorder).
        output_path: Destination .mp4 file path.
        timeout: Maximum encoding time in seconds (default 7200 = 2 hours).

    Returns:
        (success: bool, error_msg: str | None, size_bytes: int)
        size_bytes is 0 on failure.
    """
    if not os.path.exists(raw_path):
        return False, f"Raw file not found: {raw_path}", 0

    cmd = [
        "ffmpeg", "-y",
        "-i", raw_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "160k",
        output_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"Encoding timed out after {timeout} seconds", 0
    except (OSError, FileNotFoundError) as e:
        return False, f"Failed to launch ffmpeg: {e}", 0

    if result.returncode == 0 and os.path.exists(output_path):
        size_bytes = os.path.getsize(output_path)
        if size_bytes > 0:
            return True, None, size_bytes
        # ffmpeg exited 0 but file is empty — treat as failure
        try:
            os.unlink(output_path)
        except OSError:
            pass
        return False, "Encoding produced an empty output file", 0

    # Build a meaningful error from ffmpeg stderr
    error_detail = ""
    if result.stderr:
        last_lines = result.stderr.strip().splitlines()[-5:]
        error_detail = " | ".join(last_lines)
    error_msg = f"Encoding failed (exit {result.returncode})"
    if error_detail:
        error_msg += f": {error_detail}"

    return False, error_msg, 0
