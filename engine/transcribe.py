"""Audio transcription — extract audio from video, run Whisper via faster-whisper."""

import os
import subprocess
import tempfile

# Model size options: tiny (~75MB), base (~140MB), small (~460MB), medium (~1.5GB)
DEFAULT_MODEL_SIZE = "small"
_whisper_model = None


def extract_audio(video_path, output_path=None, sample_rate=16000):
    """Extract audio from video file as WAV using ffmpeg.

    Returns:
        (success: bool, wav_path: str|None, error: str|None)
    """
    if not os.path.exists(video_path):
        return False, None, f"Video file not found: {video_path}"

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        output_path = tmp.name

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(sample_rate),
        "-ac", "1",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0 and os.path.exists(output_path):
            if os.path.getsize(output_path) > 0:
                return True, output_path, None
            else:
                return False, None, "Extracted audio file is empty"
        else:
            err = ""
            if result.stderr:
                err = "\n".join(result.stderr.strip().splitlines()[-3:])
            return False, None, err or "Audio extraction failed"
    except subprocess.TimeoutExpired:
        return False, None, "Audio extraction timed out"


def is_whisper_available():
    """Check if faster-whisper is installed."""
    try:
        import faster_whisper
        return True
    except ImportError:
        return False


def get_whisper_model(model_size=None):
    """Load or return cached Whisper model.

    Args:
        model_size: "tiny", "base", "small", "medium" (default: small)

    Returns:
        faster_whisper.WhisperModel instance
    """
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    from faster_whisper import WhisperModel

    size = model_size or DEFAULT_MODEL_SIZE

    # Use CPU by default. CUDA if available.
    device = "cpu"
    compute_type = "int8"

    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            device = "cuda"
            compute_type = "float16"
    except Exception:
        pass

    _whisper_model = WhisperModel(size, device=device, compute_type=compute_type)
    return _whisper_model


def transcribe_audio(wav_path, model_size=None):
    """Transcribe audio using faster-whisper.

    Args:
        wav_path: Path to audio file (WAV, MP3, etc. — faster-whisper handles most formats)
        model_size: Whisper model size (default: small)

    Returns:
        (success: bool, transcript: str|None, error: str|None)
    """
    if not os.path.exists(wav_path):
        return False, None, f"Audio file not found: {wav_path}"

    if not is_whisper_available():
        return False, None, "faster-whisper not installed. Enable Smart Features in Settings."

    try:
        model = get_whisper_model(model_size)
        segments, info = model.transcribe(wav_path, beam_size=5)

        # Collect all segments into full transcript
        lines = []
        for segment in segments:
            lines.append(segment.text.strip())

        transcript = " ".join(lines)

        if not transcript.strip():
            return True, "", None  # Valid but empty (no speech detected)

        return True, transcript.strip(), None
    except Exception as e:
        return False, None, f"Transcription failed: {e}"


def transcribe_video(video_path, model_size=None):
    """Full pipeline: extract audio from video, then transcribe.

    Args:
        video_path: Path to video file (MP4, MKV, etc.)
        model_size: Whisper model size (default: small)

    Returns:
        (success: bool, transcript: str|None, error: str|None)
    """
    # Extract audio
    success, wav_path, error = extract_audio(video_path)
    if not success:
        return False, None, f"Audio extraction failed: {error}"

    try:
        success, transcript, error = transcribe_audio(wav_path, model_size=model_size)
        return success, transcript, error
    finally:
        try:
            if wav_path and os.path.exists(wav_path):
                os.unlink(wav_path)
        except OSError:
            pass
