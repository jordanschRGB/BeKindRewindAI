"""Structured error codes for MemoryVault.

Error codes provide machine-readable identifiers for errors, enabling:
- Consistent error handling across the codebase
- Actionable user guidance based on error patterns
- Better debugging and log analysis

Format: CODE_NAME = (code_value, human_message, guidance_dict)
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ErrorCode:
    """A structured error code with message and guidance."""
    code: str
    message: str
    guidance: Optional[dict] = None

    def __str__(self):
        return self.message


ERROR_CODES = {

    "NO_SESSION": ErrorCode(
        "NO_SESSION",
        "No active capture session. Start a session with POST /api/session/start.",
        {"session": "Start a new session with POST /api/session/start"},
    ),

    "NO_CONFIG": ErrorCode(
        "NO_CONFIG",
        "No device configuration found. Run the setup wizard first.",
        {"setup": "Run the setup wizard at http://127.0.0.1:5000/setup or use 'bekindrewind doctor' to diagnose"},
    ),

    "INVALID_CONFIG": ErrorCode(
        "INVALID_CONFIG",
        "Invalid device configuration provided.",
        {"video": "Ensure 'video' device is selected", "audio": "Ensure 'audio' device is selected"},
    ),

    "CAPTURE_TEST_FAILED": ErrorCode(
        "CAPTURE_TEST_FAILED",
        "Test capture failed. The selected devices may be unavailable or busy.",
        {
            "Device not found": "Run 'bekindrewind doctor' to check device detection",
            "Permission denied": "Check USB permissions on Linux: ls -la /dev/video*",
            "Invalid": "Try re-selecting your capture device in setup",
            "busy": "Close other programs using the capture device",
        },
    ),

    "CAPTURE_FAILED": ErrorCode(
        "CAPTURE_FAILED",
        "Recording failed. Check device connection and try again.",
        {
            "Device not found": "Run 'bekindrewind doctor' to verify devices are detected",
            "No such file": "Check that your capture device is still connected",
            "I/O error": "Try a different USB port or check cable connections",
            "signal": "Ensure your VCR is playing and the capture device shows a video signal",
        },
    ),

    "NO_SIGNAL": ErrorCode(
        "NO_SIGNAL",
        "No video signal detected from your VCR/capture device.",
        {
            "blank": "Ensure the VCR is playing and the capture card shows video",
            "signal": "Check cable connections between VCR and capture device",
        },
    ),

    "ENCODING_FAILED": ErrorCode(
        "ENCODING_FAILED",
        "Failed to encode raw recording to MP4.",
        {
            "ffmpeg": "Run 'bekindrewind doctor' to check ffmpeg installation",
            "corrupt": "The raw recording file may be corrupted. Try capturing again",
        },
    ),

    "VALIDATION_FAILED": ErrorCode(
        "VALIDATION_FAILED",
        "Recording did not pass validation checks.",
        {
            "no audio": "Check that your audio cable is properly connected",
            "no video": "Check that your video cable is properly connected",
            "blank": "The tape may be blank or the VCR head may need cleaning",
            "too short": "Recording was shorter than 10 seconds. Ensure tape is playing",
        },
    ),

    "TRANSCRIPTION_FAILED": ErrorCode(
        "TRANSCRIPTION_FAILED",
        "Speech-to-text transcription failed.",
        {
            "not installed": "Install faster-whisper: pip install faster-whisper",
            "no audio": "Ensure the recording has audio track",
            "model": "Try re-downloading the Whisper model",
        },
    ),

    "LABELING_FAILED": ErrorCode(
        "LABELING_FAILED",
        "AI labeling failed. The transcript was still saved.",
        {
            "model not found": "Download the Qwen model in Settings > AI",
            "API": "Check your API configuration in Settings > AI",
            "timeout": "Try again or reduce transcript length",
        },
    ),

    "FFMPEG_NOT_FOUND": ErrorCode(
        "FFMPEG_NOT_FOUND",
        "ffmpeg not found. MemoryVault requires ffmpeg for recording and encoding.",
        {"ffmpeg": "Run 'bekindrewind doctor' for automatic ffmpeg installation"},
    ),

    "DEVICE_NOT_FOUND": ErrorCode(
        "DEVICE_NOT_FOUND",
        "Capture device not found. It may have been disconnected or permissions changed.",
        {
            "video": "Check USB connections and run 'bekindrewind doctor'",
            "/dev/video": "On Linux, check: ls -la /dev/video* and sudo chmod 666 /dev/video*",
        },
    ),

    "NOT_FOUND": ErrorCode(
        "NOT_FOUND",
        "The requested resource was not found.",
        None,
    ),

    "DELETE_FAILED": ErrorCode(
        "DELETE_FAILED",
        "Failed to delete the recording.",
        {
            "Permission denied": "Check file permissions manually",
            "in use": "Close any programs that may be using the file",
        },
    ),

    "EXPORT_FAILED": ErrorCode(
        "EXPORT_FAILED",
        "Failed to export library data.",
        None,
    ),

    "INVALID_FORMAT": ErrorCode(
        "INVALID_FORMAT",
        "Invalid export format. Use 'json' or 'csv'.",
        None,
    ),

    "INVALID_STATE": ErrorCode(
        "INVALID_STATE",
        "Operation not allowed in current session state.",
        None,
    ),

    "DISK_FULL": ErrorCode(
        "DISK_FULL",
        "Disk is full. Free up space to continue recording.",
        {
            "disk": "Check disk space: df -h",
        },
    ),

    "MODEL_NOT_DOWNLOADED": ErrorCode(
        "MODEL_NOT_DOWNLOADED",
        "AI model not downloaded. Go to Settings > AI to download models.",
        None,
    ),

    "API_CONFIG_MISSING": ErrorCode(
        "API_CONFIG_MISSING",
        "API configuration is missing. Set up API access in Settings > AI.",
        None,
    ),

    "WHISPER_UNAVAILABLE": ErrorCode(
        "WHISPER_UNAVAILABLE",
        "Whisper transcription is not available. Install faster-whisper to enable.",
        {
            "pip": "Run: pip install faster-whisper",
            "not installed": "The faster-whisper package failed to load",
        },
    ),

    "LLAMA_CPP_UNAVAILABLE": ErrorCode(
        "LLAMA_CPP_UNAVAILABLE",
        "llama-cpp-python is not installed. AI labeling requires it.",
        {
            "pip": "Run: pip install llama-cpp-python",
            "Apple Silicon": "For Mac M1/M2/M3: pip install llama-cpp-python with --force-reinstall --no-cache-dir",
        },
    ),

    "AI_FAILURE": ErrorCode(
        "AI_FAILURE",
        "AI processing failed. Recording and transcript were saved without AI enhancements.",
        {
            "timeout": "Try again or disable AI labeling in Settings",
            "model": "Check Settings > AI to verify model downloads",
            "API": "Check your API configuration",
        },
    ),

    "PIPELINE_ERROR": ErrorCode(
        "PIPELINE_ERROR",
        "An error occurred during the capture pipeline.",
        {
            "device": "Run 'bekindrewind doctor' to diagnose device issues",
            "ffmpeg": "Check ffmpeg is working: ffmpeg -version",
            "disk": "Ensure you have disk space available",
        },
    ),
}


def get_error(code_name: str) -> ErrorCode:
    """Get an ErrorCode by name. Returns a generic error if not found."""
    return ERROR_CODES.get(code_name, ErrorCode(
        code_name,
        f"An error occurred (code: {code_name}).",
        None,
    ))


def get_error_dict(code_name: str) -> dict:
    """Get an error response dict for API endpoints."""
    error = get_error(code_name)
    result = {"error": error.message, "code": error.code}
    if error.guidance:
        result["guidance"] = error.guidance
    return result


def format_error_message(code_name: str, context: str = "") -> str:
    """Format an error message with optional context.

    Args:
        code_name: The error code name
        context: Additional context about what failed

    Returns:
        Formatted error message string
    """
    error = get_error(code_name)
    if context:
        return f"{error.message} {context}"
    return error.message


def check_error_for_guidance(error_msg: str) -> Optional[str]:
    """Check an error message against known patterns and return guidance.

    Args:
        error_msg: The error message to check

    Returns:
        Guidance string if a match is found, None otherwise
    """
    for code_name, error in ERROR_CODES.items():
        if error.guidance:
            for hint_key, hint_text in error.guidance.items():
                if hint_key.lower() in error_msg.lower():
                    return hint_text
    return None
