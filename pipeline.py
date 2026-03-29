"""Capture pipeline — orchestrates record -> encode -> validate -> save."""

import os
import re
import threading
import time

from engine.capture import Recorder, check_video_signal, _build_capture_cmd
from engine.encode import encode_to_mp4
from engine.validate import validate_capture
from engine.logging_ import get_logger
from engine.errors import get_error_dict, check_error_for_guidance
from library import save_metadata
from session import Session, SessionState

logger = get_logger("pipeline")


def safe_filename(name):
    name = name.strip()
    name = re.sub(r"[^\w\-]", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_") or "tape"


def run_tape_pipeline(session, config, on_complete=None):
    thread = threading.Thread(
        target=_pipeline_thread,
        args=(session, config, on_complete),
        daemon=True,
    )
    thread.start()
    return thread


def _pipeline_thread(session, config, on_complete):
    tape = session.tapes[-1]
    tape_num = tape["number"]
    output_dir = session.output_dir

    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    if tape["name"]:
        base_name = f"{safe_filename(tape['name'])}_{timestamp}"
    else:
        base_name = f"Tape_{tape_num:03d}_{timestamp}"

    raw_path = os.path.join(output_dir, f"{base_name}_raw.mkv")
    final_path = os.path.join(output_dir, f"{base_name}.mp4")

    session.set_state(SessionState.RECORDING)
    tape["status"] = "recording"
    logger.info("Starting recording for tape %d: %s", tape_num, base_name)

    cmd = _build_capture_cmd(config["video"], config["audio"], raw_path)
    recorder = Recorder(cmd, raw_path)
    session._recorder = recorder
    recorder.start()

    while recorder.is_running() and not recorder.stopped:
        time.sleep(0.5)

    if not recorder.stopped:
        recorder.stop()

    elapsed = recorder.elapsed()
    tape["duration_raw"] = int(elapsed)
    tape["stop_reason"] = recorder.stop_reason or "manual"

    if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
        tape["status"] = "failed"
        tape["error"] = "Recording produced no output"
        session.complete_tape({"valid": False, "error": "No output"})
        logger.error("CAPTURE_FAILED: Recording produced no output for tape %s", tape_num)
        if on_complete:
            on_complete(session)
        return

    session.set_state(SessionState.ENCODING)
    tape["status"] = "encoding"
    logger.info("Encoding tape %d...", tape_num)

    success, err, size = encode_to_mp4(raw_path, final_path)

    if success:
        try:
            os.unlink(raw_path)
        except OSError:
            pass
        tape["file"] = final_path
        logger.info("Encoding complete: %s", final_path)
    else:
        tape["file"] = raw_path
        tape["encode_error"] = err
        logger.error("ENCODING_FAILED: %s", err)

    session.set_state(SessionState.VALIDATING)
    tape["status"] = "validating"
    logger.info("Validating tape %d...", tape_num)

    validation = validate_capture(tape["file"])
    tape["validation"] = validation

    metadata = {
        "base_name": base_name,
        "filename": os.path.basename(tape["file"]),
        "duration_seconds": validation.get("duration_seconds", 0),
        "size_bytes": validation.get("size_bytes", 0),
        "captured_at": tape.get("started_at", ""),
        "stop_reason": tape.get("stop_reason", ""),
        "validation": {
            "has_audio": validation.get("has_audio", False),
            "has_video": validation.get("has_video", False),
            "not_blank": validation.get("valid", False),
            "duration_ok": validation.get("duration_seconds", 0) >= 10,
        },
    }
    save_metadata(output_dir, base_name, metadata)

    # AI post-processing
    try:
        # Transcription via faster-whisper (no model download needed — auto-downloads)
        from engine.transcribe import is_whisper_available, transcribe_video as whisper_transcribe
        if is_whisper_available():
            t_success, transcript, t_err = whisper_transcribe(tape["file"])
            if t_success and transcript:
                metadata["transcript"] = transcript
                logger.info("Transcription complete: %d chars", len(transcript))
            elif t_err:
                logger.warning("TRANSCRIPTION_FAILED: %s", t_err)

        # Smart labeling via Qwen (needs GGUF model downloaded)
        from engine.inference import is_model_downloaded
        if is_model_downloaded("qwen-labeler"):
            from engine.labeler import label_video
            transcript_text = metadata.get("transcript", "")
            l_success, labels, l_err = label_video(tape["file"], transcript=transcript_text)
            if l_success and labels:
                metadata["labels"] = labels
                logger.info("Labels generated: %s", labels.get("title", "untitled"))
                if labels.get("title"):
                    new_base = safe_filename(labels["title"]) + "_" + timestamp
                    new_final = os.path.join(output_dir, f"{new_base}.mp4")
                    if tape["file"] != new_final:
                        try:
                            os.rename(tape["file"], new_final)
                            tape["file"] = new_final
                            metadata["filename"] = os.path.basename(new_final)
                        except OSError as e:
                            logger.warning("Failed to rename file to labeled name: %s", e)
            elif l_err:
                logger.warning("LABELING_FAILED: %s", l_err)

        # Re-save metadata with AI data
        save_metadata(output_dir, base_name, metadata)
    except Exception as e:
        # AI failures never block the pipeline, but we log them now
        logger.warning("AI_FAILURE: AI post-processing failed: %s", e)

    session.complete_tape(validation, file_path=tape["file"])

    if on_complete:
        on_complete(session)


def stop_recording(session):
    recorder = getattr(session, "_recorder", None)
    if recorder and recorder.is_running():
        recorder.stop_reason = "user"
        recorder.stop()
        logger.info("Recording stopped by user")
