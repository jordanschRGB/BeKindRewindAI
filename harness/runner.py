"""MemoryVault Nanobot Runner — wires the Archivist through Nanobot's agent loop.

This is the production orchestrator. smolagents is the portfolio demo.
This is what ships.

The pipeline is deterministic. The model fills in blanks, not decisions.
"""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nanobot.agent.tools.registry import ToolRegistry
from harness.tools import register_vault_tools, VAULT_DIR, MEMORY_DIR

from engine.labeler import (
    _call_api, get_api_url, get_api_key, get_model_name, _parse_labels,
    load_ai_config,
)
from agent import (
    DOMAIN_PRESETS, WHISPER_BRIEFING,
    worker_generate_vocabulary, scorer_rate_output,
    load_memory, append_memory, append_vocabulary, append_session_log,
)

# ── Agent Prompts (isolated context per role) ─────────────────────────────────

ARCHIVIST_PROMPT = """You are the Archivist. You run entirely on this computer — nothing leaves this machine.
You help people digitize VHS tapes. Be warm, be brief, be honest about what you are.
When you ask about tapes, explain why: it helps you understand the audio better."""

WORKER_VOCAB_PROMPT = """Generate a comma-separated vocabulary list for Whisper speech recognition.
Focus on proper nouns, foreign terms, and domain words Whisper would mangle.
15-40 words, hardest first. No common English. No sentences. Just the word list."""

WORKER_LABEL_PROMPT = """Generate a title, description, and tags for this VHS tape based on the transcript.
Respond with ONLY a JSON object: {"title": "...", "description": "...", "tags": ["..."]}
Keep the title under 60 characters. Ground everything in the transcript — no hallucinated names."""

SCORER_PROMPT = """Rate this label 1-10. If below 7, state what the user would have to do because of the error.
Respond with ONLY JSON: {"score": N, "reason": "...", "consequence": "..." or null}"""


def _call_llm(system_prompt, user_content):
    """Single inference call with isolated context. Returns response text or None."""
    api_url = get_api_url()
    if not api_url:
        return None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    success, text, err = _call_api(
        messages, api_url=api_url, api_key=get_api_key(), model=get_model_name(),
    )
    return text if success else None


# ── Pipeline Steps (deterministic, harness-controlled) ────────────────────────

def step_greet(memory_text):
    """Archivist greets the user with memory context."""
    context = "Previous memory:\n" + memory_text if memory_text else "No previous sessions."
    response = _call_llm(
        ARCHIVIST_PROMPT,
        f"{context}\n\nGreet the user. Ask what kind of tapes they have and explain why you're asking."
    )
    return response or (
        "Hey! I'm the Archivist. I run entirely on this computer — nothing leaves this machine. "
        "What kind of tapes are we working with? Knowing a bit about the content helps me "
        "understand the audio better."
    )


def step_generate_vocabulary(user_description, memory_text=""):
    """Worker generates Whisper vocabulary. Reads briefing + user description."""
    context = WHISPER_BRIEFING + "\n\n"
    if memory_text:
        context += f"Previously learned vocabulary:\n{memory_text}\n\n"
    context += f"User description: {user_description}"

    response = _call_llm(WORKER_VOCAB_PROMPT, context)
    if response:
        vocab = response.strip().strip("`").strip()
        # Save to memory for next session
        append_vocabulary(vocab)
        return vocab

    # Fallback: try to detect domain and use presets
    lower = user_description.lower()
    for domain, preset in DOMAIN_PRESETS.items():
        if any(word in lower for word in domain.split()):
            return preset
    return ""


def step_transcribe(video_path, vocabulary=""):
    """Transcribe audio with Whisper, primed with vocabulary."""
    from engine.transcribe import extract_audio, is_whisper_available

    if not is_whisper_available():
        return None, "Whisper not available"

    success, wav_path, err = extract_audio(video_path)
    if not success:
        return None, err

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
        segments, info = model.transcribe(
            wav_path, beam_size=5,
            initial_prompt=vocabulary if vocabulary else None,
        )
        transcript = " ".join(seg.text.strip() for seg in segments).strip()
        return transcript or "(no speech detected)", None
    except Exception as e:
        return None, str(e)
    finally:
        try:
            os.unlink(wav_path)
        except OSError:
            pass


def step_label(transcript):
    """Worker generates labels from transcript."""
    response = _call_llm(WORKER_LABEL_PROMPT, f"Transcript:\n{transcript}")
    if response:
        labels = _parse_labels(response)
        if labels:
            return labels, None
        return None, f"Could not parse: {response[:100]}"
    return None, "LLM unavailable"


def step_score(transcript, labels):
    """Scorer rates the label. Returns (score, reason, consequence)."""
    labels_json = json.dumps(labels)
    success, score_data, err = scorer_rate_output(transcript, labels_json)
    if success:
        return score_data["score"], score_data["reason"], score_data.get("consequence")
    return 5, "Scoring unavailable", None  # Default pass if scorer fails


def step_label_with_retry(transcript, max_retries=2):
    """Label → Score → Retry loop. Harness controls the loop, not the model."""
    last_feedback = ""

    for attempt in range(max_retries + 1):
        # Label
        prompt_extra = ""
        if last_feedback:
            prompt_extra = f"\n\nPrevious attempt scored poorly: {last_feedback}\nDo better this time."

        response = _call_llm(
            WORKER_LABEL_PROMPT,
            f"Transcript:\n{transcript}{prompt_extra}"
        )

        if not response:
            return None, "LLM unavailable"

        labels = _parse_labels(response)
        if not labels:
            last_feedback = "Output was not valid JSON."
            continue

        # Score
        score, reason, consequence = step_score(transcript, labels)

        if score >= 7:
            return labels, None

        # Build feedback for retry
        last_feedback = f"Score {score}/10. {reason}"
        if consequence:
            last_feedback += f" Consequence: {consequence}"

    # After retries, return best effort
    return labels, f"Best score after {max_retries + 1} attempts: {score}/10"


def step_save(base_name, video_path, transcript, labels, vocabulary):
    """Save metadata alongside the video file."""
    from engine.validate import validate_capture

    validation = validate_capture(video_path)

    metadata = {
        "filename": os.path.basename(video_path),
        "duration_seconds": validation.get("duration_seconds", 0),
        "size_bytes": validation.get("size_bytes", 0),
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "validation": {
            "has_audio": validation.get("has_audio", False),
            "has_video": validation.get("has_video", False),
            "not_blank": validation.get("valid", False),
            "duration_ok": validation.get("duration_seconds", 0) >= 10,
        },
        "transcript": transcript,
        "labels": labels,
        "vocabulary_used": vocabulary,
    }

    os.makedirs(VAULT_DIR, exist_ok=True)
    meta_path = os.path.join(VAULT_DIR, f"{base_name}.json")
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)

    return metadata


def step_summarize(labels, score_info=""):
    """Archivist summarizes results to the user."""
    if labels:
        title = labels.get("title", "untitled")
        desc = labels.get("description", "")
        response = _call_llm(
            ARCHIVIST_PROMPT,
            f"You just finished processing a tape. The title is: '{title}'. "
            f"Description: '{desc}'. Tell the user what you found, warmly and briefly."
        )
        return response or f"Done! I'm calling this one \"{title}\"."
    return "I processed the tape but couldn't generate a good title. You might want to rename it."


# ── Full Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(user_description, video_path):
    """Run the full deterministic pipeline for one tape.

    Args:
        user_description: What the user said about their tapes
        video_path: Path to the captured/encoded video file

    Returns:
        dict with all results
    """
    results = {"steps": []}

    def log(step, data):
        results["steps"].append({"step": step, "time": time.strftime("%H:%M:%S"), **data})

    # 1. Load memory
    memory = load_memory()
    log("memory", {"loaded": bool(memory)})

    # 2. Generate vocabulary (Worker agent, isolated context)
    vocab = step_generate_vocabulary(user_description, memory)
    log("vocabulary", {"words": len(vocab.split(",")) if vocab else 0, "sample": vocab[:100]})

    # 3. Transcribe with vocabulary priming
    transcript, err = step_transcribe(video_path, vocabulary=vocab)
    if not transcript:
        log("transcribe", {"error": err})
        results["error"] = err
        return results
    log("transcribe", {"length": len(transcript), "sample": transcript[:100]})

    # 4. Label with retry loop (Worker + Scorer, harness controls retries)
    labels, label_err = step_label_with_retry(transcript)
    log("label", {"labels": labels, "error": label_err})

    # 5. Save metadata
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    metadata = step_save(base_name, video_path, transcript, labels, vocab)
    log("save", {"file": f"{base_name}.json"})

    # 6. Log session to memory
    title = labels.get("title", "untitled") if labels else "untitled"
    append_session_log(f"Captured '{title}' from {os.path.basename(video_path)}")

    # 7. Summarize for user (Archivist agent)
    summary = step_summarize(labels)
    log("summary", {"message": summary})

    results["title"] = title
    results["transcript"] = transcript
    results["labels"] = labels
    results["summary"] = summary
    results["vocabulary"] = vocab

    return results


# ── Interactive Mode ──────────────────────────────────────────────────────────

def run_interactive():
    """Run the Archivist in interactive mode."""
    print("\n" + "=" * 50)
    print("  The Archivist")
    print("  Everything runs on this computer.")
    print("  Type 'quit' to exit.")
    print("=" * 50)

    memory = load_memory()
    greeting = step_greet(memory)
    print(f"\nArchivist: {greeting}\n")

    user_description = input("You: ").strip()
    if user_description.lower() in ("quit", "exit", "q"):
        return

    # Generate vocabulary
    print("\nArchivist: Let me tune my ears for that content...")
    vocab = step_generate_vocabulary(user_description, memory)
    print(f"  (Generated {len(vocab.split(','))} vocabulary terms)")
    print(f"\nArchivist: Got it. I'm ready. What video file should I process?")
    print("  (Paste the full path to an MP4 or MKV file)\n")

    video_path = input("You: ").strip().strip('"')
    if not os.path.exists(video_path):
        print(f"\nArchivist: I can't find that file. Check the path and try again.")
        return

    print(f"\nArchivist: Processing {os.path.basename(video_path)}...")
    results = run_pipeline(user_description, video_path)

    print(f"\nArchivist: {results.get('summary', 'Done.')}")

    if results.get("labels"):
        print(f"\n  Title: {results['labels'].get('title')}")
        print(f"  Tags:  {', '.join(results['labels'].get('tags', []))}")

    print(f"\n  Steps completed: {len(results.get('steps', []))}")
    for step in results.get("steps", []):
        print(f"    [{step['time']}] {step['step']}")

    print()


if __name__ == "__main__":
    run_interactive()
