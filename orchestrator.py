"""MemoryVault Orchestrator — smolagents-powered agent loop.

Replaces Claude Code as the framework. Handles:
- Tool registration with clear interfaces
- Agent loop (call model → parse tool use → execute → repeat)
- Logging every action and decision
- Multi-agent coordination (Archivist, Worker, Scorer)
"""

import json
import os
import time

from smolagents import (
    ToolCallingAgent,
    OpenAIServerModel,
    tool,
)

from engine.labeler import load_ai_config

# ── Tools ────────────────────────────────────────────────────────────────────
# Each tool is a self-contained action the agent can invoke.
# smolagents handles the call loop — model decides when to use each tool.


@tool
def detect_devices() -> str:
    """Detect connected video and audio capture devices.
    Returns a JSON string listing available video and audio devices.
    """
    from engine.devices import detect_video_devices, detect_audio_devices
    video = detect_video_devices()
    audio = detect_audio_devices()
    return json.dumps({
        "video": [{"label": l, "config": c} for l, c in video],
        "audio": [{"label": l, "config": c} for l, c in audio],
    })


@tool
def generate_whisper_vocabulary(user_description: str) -> str:
    """Generate a Whisper vocabulary prompt to improve transcription accuracy.
    Takes the user's description of their tapes and returns a comma-separated
    list of domain-specific words that Whisper should listen for.

    Args:
        user_description: What the user said about their tapes (content, language, names, era).
    """
    from agent import worker_generate_vocabulary
    success, vocab, err = worker_generate_vocabulary(user_description)
    if success:
        return vocab
    return f"Error: {err}"


@tool
def start_capture(video_device: str, audio_device: str, output_name: str) -> str:
    """Start recording from a capture card. This captures video and audio
    from the specified devices and saves to a raw file. Recording stops
    automatically on 10 seconds of silence or 5 seconds of black screen.
    IMPORTANT: Always confirm with the user before calling this.

    Args:
        video_device: Video device identifier (e.g. "video=Iriun Webcam")
        audio_device: Audio device identifier (e.g. "audio=Microphone (HyperX)")
        output_name: Base name for the output file (e.g. "tape_001")
    """
    import platform
    from engine.capture import Recorder

    output_dir = os.path.join(os.path.expanduser("~"), "Videos", "MemoryVault")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H%M%S")
    raw_path = os.path.join(output_dir, f"{output_name}_{timestamp}_raw.mkv")

    fmt = "dshow" if platform.system() == "Windows" else "v4l2"
    video_cfg = {"format": fmt, "device": video_device}
    audio_cfg = {"format": fmt, "device": audio_device}

    recorder = Recorder(video_cfg, audio_cfg, raw_path)
    recorder.start()

    # Wait for recording to finish (auto-stop on silence/black)
    while recorder.is_running() and not recorder.stopped:
        time.sleep(1)

    if not recorder.stopped:
        recorder.stop()

    elapsed = int(recorder.elapsed())
    stop_reason = recorder.stop_reason or "manual"

    if os.path.exists(raw_path) and os.path.getsize(raw_path) > 0:
        return json.dumps({
            "status": "ok",
            "file": raw_path,
            "duration_seconds": elapsed,
            "stop_reason": stop_reason,
        })
    else:
        return json.dumps({"status": "error", "error": "Recording produced no output"})


@tool
def encode_video(raw_path: str) -> str:
    """Encode a raw capture file to MP4 for smaller file size and compatibility.

    Args:
        raw_path: Path to the raw MKV capture file.
    """
    from engine.encode import encode_to_mp4
    final_path = raw_path.replace("_raw.mkv", ".mp4")
    success, err, size = encode_to_mp4(raw_path, final_path)
    if success:
        try:
            os.unlink(raw_path)
        except OSError:
            pass
        return json.dumps({"status": "ok", "file": final_path, "size_bytes": size})
    return json.dumps({"status": "error", "error": err, "raw_file": raw_path})


@tool
def transcribe_video_file(video_path: str, whisper_vocabulary: str) -> str:
    """Transcribe audio from a video file using Whisper speech recognition.
    The whisper_vocabulary parameter primes the decoder with domain-specific
    words to improve accuracy on unusual names and foreign terms.

    Args:
        video_path: Path to the MP4 or MKV file.
        whisper_vocabulary: Comma-separated vocabulary to prime Whisper with.
    """
    from engine.transcribe import extract_audio, is_whisper_available

    if not is_whisper_available():
        return json.dumps({"status": "error", "error": "Whisper not available"})

    # Extract audio
    success, wav_path, err = extract_audio(video_path)
    if not success:
        return json.dumps({"status": "error", "error": err})

    try:
        from faster_whisper import WhisperModel
        import ctranslate2

        device = "cpu"
        compute_type = "int8"
        try:
            if ctranslate2.get_cuda_device_count() > 0:
                device = "cuda"
                compute_type = "float16"
        except Exception:
            pass

        model = WhisperModel("small", device=device, compute_type=compute_type)

        # Use the vocabulary as initial_prompt — this is the key insight
        segments, info = model.transcribe(
            wav_path,
            beam_size=5,
            initial_prompt=whisper_vocabulary if whisper_vocabulary else None,
        )

        lines = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                lines.append(f"{seg.start:.1f}-{seg.end:.1f}: {text}")
        transcript = " ".join(lines).strip()

        return json.dumps({
            "status": "ok",
            "transcript": transcript or "(no speech detected)",
            "language": info.language,
            "duration": info.duration,
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


@tool
def label_tape(transcript: str) -> str:
    """Generate a title, description, and tags for a tape based on its transcript.
    Returns JSON with title, description, and tags fields.

    Args:
        transcript: The text transcript of the tape's audio content.
    """
    from engine.labeler import generate_labels
    success, labels, err = generate_labels(transcript=transcript)
    if success:
        return json.dumps({"status": "ok", "labels": labels})
    return json.dumps({"status": "error", "error": err})


@tool
def score_label(transcript: str, labels_json: str) -> str:
    """Rate the quality of a generated label. Returns a score from 1-10
    with a reason and human consequence for scores below 7.
    Use this to check label quality before saving.

    Args:
        transcript: The original transcript the label was generated from.
        labels_json: The JSON string of the generated label to evaluate.
    """
    from agent import scorer_rate_output
    success, score_data, err = scorer_rate_output(transcript, labels_json)
    if success:
        return json.dumps({"status": "ok", **score_data})
    return json.dumps({"status": "error", "error": err})


@tool
def save_tape_metadata(output_dir: str, base_name: str, metadata_json: str) -> str:
    """Save tape metadata (title, transcript, labels, validation) to a JSON file
    alongside the video file.

    Args:
        output_dir: Directory where the video file is saved.
        base_name: Base filename without extension.
        metadata_json: JSON string with all metadata to save.
    """
    from library import save_metadata
    try:
        metadata = json.loads(metadata_json)
        save_metadata(output_dir, base_name, metadata)
        return json.dumps({"status": "ok", "file": f"{base_name}.json"})
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@tool
def read_memory() -> str:
    """Read the Archivist's memory file. Contains user preferences,
    learned vocabulary, and session history from previous runs.
    """
    from agent import load_memory
    memory = load_memory()
    return memory if memory else "(no memory yet)"


@tool
def save_to_memory(section: str, entry: str) -> str:
    """Save an entry to the Archivist's memory file under a specific section.
    The memory file is a plain markdown file the user can read and edit.

    Args:
        section: Section name (e.g. "User Preferences", "Vocabulary", "Sessions")
        entry: The text to append to that section.
    """
    from agent import append_memory
    append_memory(section, entry)
    return f"Saved to memory: [{section}] {entry}"


# ── Model + Agent Setup ─────────────────────────────────────────────────────

def create_model():
    """Create the LLM model from saved config."""
    config = load_ai_config()
    api_url = config.get("api_url", "http://localhost:6942/v1")
    api_key = config.get("api_key", "")
    model_id = config.get("model", "qwen3.5-4b")

    # smolagents wants base URL without /chat/completions
    base_url = api_url.replace("/chat/completions", "")

    return OpenAIServerModel(
        model_id=model_id,
        api_base=base_url,
        api_key=api_key or "none",
    )


ARCHIVIST_SYSTEM = """You are the Archivist — MemoryVault's AI assistant. You run entirely on this computer. Nothing leaves this machine.

You help people digitize their VHS tapes. You are warm, patient, and transparent.

Your workflow:
1. Read your memory file first to see if you know this user
2. Ask what kind of tapes they have — explain this helps you understand the audio better
3. Generate Whisper vocabulary from their description
4. Guide them through recording each tape (confirm before starting)
5. After capture, encode the video, transcribe it, then generate labels
6. Score the labels — if below 7, retry with the scorer's feedback
7. Save metadata and update your memory

Rules:
- Always confirm before start_capture
- Explain what you're doing at each step in plain language
- If something fails, explain simply and suggest a fix
- Save useful vocabulary and preferences to memory for next time
- Keep responses short (2-3 sentences) unless explaining something"""


def create_archivist():
    """Create the Archivist agent with all tools."""
    model = create_model()

    return ToolCallingAgent(
        tools=[
            detect_devices,
            generate_whisper_vocabulary,
            start_capture,
            encode_video,
            transcribe_video_file,
            label_tape,
            score_label,
            save_tape_metadata,
            read_memory,
            save_to_memory,
        ],
        model=model,
        instructions=ARCHIVIST_SYSTEM,
        max_steps=20,
        verbosity_level=1,
    )


# ── Run ──────────────────────────────────────────────────────────────────────

def run_interactive():
    """Run the Archivist in interactive chat mode."""
    print("Starting the Archivist...")
    archivist = create_archivist()

    print("\n" + "=" * 50)
    print("  The Archivist is ready.")
    print("  Type 'quit' to exit.")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye! Your tapes are safe.")
                break

            response = archivist.run(user_input)
            print(f"\nArchivist: {response}\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nSomething went wrong: {e}\n")


if __name__ == "__main__":
    run_interactive()
