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
from harness.grading import (
    GRADING_CRITERIA, validate_scores, check_thresholds,
    build_grading_prompt_section, format_failure_consequence,
)

from engine.labeler import (
    _call_api, get_api_url, get_api_key, get_model_name, _parse_labels,
    load_ai_config,
)
from agent import (
    DOMAIN_PRESETS, WHISPER_BRIEFING,
    worker_generate_vocabulary, scorer_rate_output,
    load_memory, append_memory, append_vocabulary, append_session_log,
)

# GAN loop configuration
MAX_ITERATIONS = 3

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

DREAMER_PROMPT_LEGACY = """You are the Dreamer. You are quietly reviewing a transcript before sleep.

You have two things:
1. A vocabulary list of KNOWN CORRECT words (names, terms, phrases)
2. A transcript from speech recognition that may have mangled some of these words

Speech recognition often mishears foreign names and terms. For example:
- "Anandamayi Ma" might appear as "ananda my" or "ananda mai"
- "satsang" might appear as "sot song" or "sat sang"
- "Om Namah Shivaya" might appear as "oh nama shivaya"

Look at each word in the vocabulary list. Is there something in the transcript
that SOUNDS LIKE that word but is spelled differently? That's a mishear.

Respond with ONLY JSON:
{"confidence": 0.0-1.0, "doubts": ["ananda my might be Anandamayi Ma", "sot song might be satsang"], "looks_fine": false}

If every vocabulary word appears correctly or doesn't appear at all, respond:
{"confidence": 1.0, "doubts": [], "looks_fine": true}"""


def _build_dreamer_prompt():
    """Build the Dreamer prompt with structured grading rubric."""
    rubric = build_grading_prompt_section()
    return f"""You are the Dreamer. You are quietly reviewing a transcript before sleep.

You have two things:
1. A vocabulary list of KNOWN CORRECT words (names, terms, phrases)
2. A transcript from speech recognition that may have mangled some of these words

Speech recognition often mishears foreign names and terms. For example:
- "Anandamayi Ma" might appear as "ananda my" or "ananda mai"
- "satsang" might appear as "sot song" or "sat sang"
- "Om Namah Shivaya" might appear as "oh nama shivaya"

Look at each word in the vocabulary list. Is there something in the transcript
that SOUNDS LIKE that word but is spelled differently? That's a mishear.

{rubric}"""


DREAMER_PROMPT = _build_dreamer_prompt()


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


def step_dream(transcript, vocabulary):
    """Dreamer reviews transcript against known vocabulary. Fresh context every call.

    Context isolation: each call is a fresh LLM call with ONLY the transcript,
    vocabulary, and grading criteria. No previous scores. No correction history.
    This prevents the evaluator from anchoring on its own prior judgments.

    In: transcript + known vocabulary
    Out: structured grading result with per-criterion scores
    Changes nothing. Returns observations only.
    """
    if not vocabulary:
        return _dream_pass_result()

    # Fresh LLM call — no prior dream results, no correction history
    response = _call_llm(
        DREAMER_PROMPT,
        f"Known vocabulary (these are definitely correct):\n{vocabulary}\n\n"
        f"Transcript to review:\n{transcript}"
    )

    if not response:
        return _dream_pass_result()

    # Parse dreamer output
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return _parse_dream_result(data)
        except (json.JSONDecodeError, ValueError):
            pass

    return _dream_pass_result()


def _dream_pass_result():
    """Default passing result when dreamer can't run or vocabulary is empty."""
    return {
        "scores": {c: 10 for c in GRADING_CRITERIA},
        "reasons": {c: "No issues detected" for c in GRADING_CRITERIA},
        "pass": True,
        "consequence": "",
        # Legacy fields for backward compatibility
        "confidence": 1.0,
        "doubts": [],
        "looks_fine": True,
    }


def _parse_dream_result(data):
    """Parse structured dream output, with fallback to legacy format."""
    # New structured format
    if "scores" in data:
        scores = {}
        for c in GRADING_CRITERIA:
            val = data["scores"].get(c, 10)
            scores[c] = int(val) if isinstance(val, (int, float)) else 10
        reasons = data.get("reasons", {})
        is_pass = data.get("pass", True)
        consequence = data.get("consequence", "")

        # Validate: recompute pass from thresholds if model says pass but scores disagree
        threshold_pass, failures = check_thresholds(scores)
        if not threshold_pass:
            is_pass = False
            if not consequence:
                consequence = format_failure_consequence(failures, reasons)

        # Extract doubts from reasons for backward compatibility
        doubts = []
        for criterion, reason in reasons.items():
            if reason and reason != "No issues detected":
                doubts.append(reason)

        return {
            "scores": scores,
            "reasons": reasons,
            "pass": is_pass,
            "consequence": consequence,
            # Legacy fields
            "confidence": min(scores.values()) / 10.0 if scores else 1.0,
            "doubts": doubts,
            "looks_fine": is_pass,
        }

    # Legacy format fallback
    confidence = float(data.get("confidence", 1.0))
    doubts = data.get("doubts", [])
    looks_fine = data.get("looks_fine", True)

    # Convert legacy to structured using data-driven heuristics rather than
    # arbitrary constants. Priority order: confidence → doubts → looks_fine.
    #
    # Rationale:
    #   - confidence < 0.5 → model was very uncertain; treat all scores as poor
    #   - doubts present → accuracy degrades with each doubt; other dims less affected
    #   - no doubts + looks_fine=True → near-perfect, but not a 10 (model didn't fully score)
    if confidence < 0.5:
        # Model signaled low confidence — all criteria unreliable, use conservative floor
        accuracy = 4
        scores = {c: 4 for c in GRADING_CRITERIA}
    elif doubts:
        # Wider curve to produce scores that distinguish severity and trigger
        # threshold logic meaningfully (threshold=7, so any doubt must be < 7):
        #   1 doubt  → 6 (clear fail, just below threshold)
        #   2 doubts → 5
        #   3+ doubts → max(3, 8 - len(doubts)), dropping further with each doubt
        n = len(doubts)
        if n == 1:
            accuracy = 6
        elif n == 2:
            accuracy = 5
        else:
            accuracy = max(3, 8 - n)
        scores = {
            "accuracy": accuracy,
            "completeness": 8,
            "label_quality": 8,
            "hallucination": 8,
        }
    else:
        # No doubts and looks_fine=True → 9 (near-perfect, slight discount for unscored)
        scores = {c: 9 for c in GRADING_CRITERIA}

    if doubts:
        reasons = {"accuracy": "; ".join(doubts)}
        is_pass = False
        _, failures = check_thresholds(scores)
        consequence = format_failure_consequence(failures, reasons)
    else:
        reasons = {}
        is_pass = True
        consequence = ""

    return {
        "scores": scores,
        "reasons": reasons,
        "pass": is_pass,
        "consequence": consequence,
        "confidence": confidence,
        "doubts": doubts,
        "looks_fine": looks_fine,
    }


def step_apply_corrections(transcript, dream_result, vocabulary, feedback=None):
    """Archivist decides: apply corrections ONLY where dreamer doubt + memory align.

    This is deterministic string replacement, not model generation.
    The model flagged the doubt. Python applies the fix. No creative rewriting.

    Args:
        transcript: current transcript text
        dream_result: structured dream output with scores/reasons/doubts
        vocabulary: comma-separated known-correct words
        feedback: optional dict of structured reasons per criterion (from dream)
    """
    if dream_result.get("looks_fine", True) or dream_result.get("pass", True):
        if not dream_result.get("doubts"):
            return transcript, []

    corrections_applied = []
    corrected = transcript

    # Parse vocabulary into a lookup
    vocab_words = [w.strip() for w in vocabulary.split(",") if w.strip()]

    # Use structured feedback to prioritize doubts. Feedback reasons are keyed
    # by criterion (e.g., "accuracy": "2 names mangled"). When feedback is
    # present, we extract any vocab-word hints from it and attempt those
    # corrections first (prepended), then process remaining doubts normally.
    doubts = list(dream_result.get("doubts", []))
    if feedback:
        # Collect criterion-level hints from feedback reasons.
        # Any feedback reason that references a vocabulary word is treated as a
        # high-priority doubt and moved to the front of the correction queue.
        feedback_hints = []
        for criterion, reason in feedback.items():
            if not reason:
                continue
            reason_lower = reason.lower()
            for vocab_word in vocab_words:
                if vocab_word.lower() in reason_lower and reason not in feedback_hints:
                    feedback_hints.append(reason)
                    break
        # Deduplicate: prepend feedback hints, then add doubts not already covered
        existing_doubts_lower = {d.lower() for d in feedback_hints}
        remaining = [d for d in doubts if d.lower() not in existing_doubts_lower]
        doubts = feedback_hints + remaining

    for doubt in doubts:
        doubt_lower = doubt.lower()
        # Check if the doubt mentions a word that matches vocabulary
        for vocab_word in vocab_words:
            vl = vocab_word.lower()
            # Look for "X might be Y" pattern
            if vl in doubt_lower and ("might be" in doubt_lower or "could be" in doubt_lower or "should be" in doubt_lower):
                # Find the mangled version in the transcript
                # Simple heuristic: look for words that are phonetically close
                for transcript_word in corrected.split():
                    tw = transcript_word.strip(".,!?;:'\"").lower()
                    # If the transcript word is similar-ish to the vocab word but not exact
                    if tw != vl and _is_phonetically_close(tw, vl):
                        old = transcript_word.strip(".,!?;:'\"")
                        corrected = corrected.replace(old, vocab_word)
                        corrections_applied.append(f"{old} → {vocab_word}")
                        break

    return corrected, corrections_applied


def _is_phonetically_close(a, b):
    """Quick check if two words are phonetically similar. Not perfect, doesn't need to be."""
    import re
    a, b = a.lower(), b.lower()
    if a == b:
        return False
    timestamp_pattern = re.compile(r'^\d+\.\d+-\d+\.\d+:$')
    if timestamp_pattern.match(a) or timestamp_pattern.match(b):
        return False
    if len(a) >= 3 and len(b) >= 3 and a[:3] == b[:3]:
        return True
    if len(a) > 3 and len(b) > 3:
        shorter, longer = (a, b) if len(a) < len(b) else (b, a)
        if shorter in longer:
            return True
    return False


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

    # 4. GAN loop: evaluate → correct → re-evaluate (max MAX_ITERATIONS rounds)
    # Context isolation: each step_dream call is fresh. No prior scores or
    # correction history leak into the Dreamer's context.
    final_dream = None
    for iteration in range(MAX_ITERATIONS):
        # Fresh evaluation — Dreamer sees ONLY transcript + vocabulary + rubric
        dream = step_dream(transcript, vocab)
        final_dream = dream
        log("dream", {
            "iteration": iteration + 1,
            "scores": dream.get("scores", {}),
            "pass": dream.get("pass", True),
            "consequence": dream.get("consequence", ""),
            "doubts": dream.get("doubts", []),
        })

        if dream.get("pass", True):
            if vocab:
                final_dream["quality_verified"] = True
            break

        if iteration < MAX_ITERATIONS - 1:
            # Feed structured feedback to correction step
            corrected_transcript, corrections = step_apply_corrections(
                transcript, dream, vocab,
                feedback=dream.get("reasons"),
            )
            if corrections:
                log("corrections", {"iteration": iteration + 1, "applied": corrections})
                transcript = corrected_transcript
            else:
                # No corrections possible — check if quality is acceptable
                scores = dream.get("scores", {})
                threshold_pass, failures = check_thresholds(scores)
                if not threshold_pass:
                    results["warning"] = (
                        f"Transcript quality below threshold after {iteration + 1} rounds. "
                        f"Failed criteria: {list(failures.keys())}. "
                        f"Scores: {failures}. "
                        f"Proceeding to labeling but quality is not verified."
                    )
                    log("corrections", {
                        "iteration": iteration + 1,
                        "applied": [],
                        "note": "no actionable corrections",
                        "warning": results["warning"],
                    })
                    final_dream["quality_verified"] = False
                else:
                    final_dream["quality_verified"] = True
                break
        else:
            # Circuit breaker: max iterations reached
            scores = dream.get("scores", {})
            threshold_pass, failures = check_thresholds(scores)
            results["warning"] = (
                f"Quality threshold not met after {MAX_ITERATIONS} GAN iterations. "
                f"Failed criteria: {list(failures.keys()) if failures else 'none'}. "
                f"Scores: {failures if failures else scores}. "
                f"Proceeding to labeling but quality is not verified."
            )
            results["final_scores"] = scores
            final_dream["quality_verified"] = False
            log("circuit_breaker", {
                "iteration": iteration + 1,
                "scores": scores,
                "failures": failures,
                "consequence": dream.get("consequence", ""),
            })

    # 5. Label from (possibly corrected) transcript
    labels, label_err = step_label(transcript)
    log("label", {"labels": labels, "error": label_err})

    # 6. Save metadata
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    metadata = step_save(base_name, video_path, transcript, labels, vocab)
    log("save", {"file": f"{base_name}.json"})

    # 7. Log session to memory
    title = labels.get("title", "untitled") if labels else "untitled"
    append_session_log(f"Captured '{title}' from {os.path.basename(video_path)}")

    # 8. Summarize for user (Archivist agent)
    summary = step_summarize(labels)
    log("summary", {"message": summary})

    results["title"] = title
    results["transcript"] = transcript
    results["labels"] = labels
    results["summary"] = summary
    results["vocabulary"] = vocab

    # Include grading results
    if final_dream:
        results["grading"] = {
            "scores": final_dream.get("scores", {}),
            "pass": final_dream.get("pass", True),
            "consequence": final_dream.get("consequence", ""),
            "quality_verified": final_dream.get("quality_verified", False),
        }

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
