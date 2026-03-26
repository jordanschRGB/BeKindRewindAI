"""MemoryVault Agent — conversational interface that drives the capture pipeline.

The agent asks the user what they're digitizing, configures the pipeline
optimally, and guides them through the process with explicit state management.

Architecture: Three logical agents on one model, isolated context per call.
- Archivist: talks to user, drives pipeline (has conversation history + memory)
- Scorer: rates output quality, states human consequences (only sees output + transcript)
- Worker: generates vocabulary lists and labels (only sees transcript + last score)
"""

import json
import os
import time

from engine.transcribe import is_whisper_available
from engine.labeler import _call_api, get_api_url, get_api_key, get_model_name
from session import Session, SessionState

# Load skill briefings — reference docs agents read before specific tasks
SKILLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


def _load_skill(name):
    """Load a skill briefing markdown file."""
    path = os.path.join(SKILLS_DIR, f"{name}.md")
    if os.path.exists(path):
        with open(path) as f:
            return f.read()
    return ""


WHISPER_BRIEFING = _load_skill("whisper_briefing")

# Domain vocabulary presets for Whisper initial_prompt
DOMAIN_PRESETS = {
    "spiritual": "Om Namah Shivaya, satsang, kirtan, dharma, sangha, pranayama, Anandamayi, ashram, mantra, puja, bhajan, guru, swami, meditation, breathwork, ceremony, chakra, kundalini, tantra, vedanta, sutra, namaste",
    "family": "birthday, Christmas, Thanksgiving, wedding, graduation, baby, kids, grandma, grandpa, vacation, holiday, backyard, kitchen, living room",
    "sports": "game, score, team, coach, practice, tournament, championship, halftime, quarterback, touchdown, goal, foul, referee",
    "music": "concert, band, guitar, drums, bass, vocals, solo, encore, setlist, venue, stage, amp, microphone",
    "church": "sermon, pastor, reverend, congregation, hymn, choir, prayer, scripture, gospel, communion, baptism, altar, fellowship",
    "general": "",
}

# System prompt for the agent's conversational behavior
AGENT_SYSTEM = """You are the Archivist — MemoryVault's assistant. You help people digitize their VHS tapes and cassettes.

IMPORTANT IDENTITY RULES:
- Your name is "the Archivist"
- You run ENTIRELY on this computer. No internet. No cloud. Nothing leaves this machine. Say this early.
- When you ask about the tapes, explain WHY: "Knowing what's on the tapes helps me understand the audio better — names, languages, and topics I should listen for."
- Be transparent about every step: "I'm about to start recording" / "I'm listening to the audio now" / "I'm generating a title based on what I heard"
- Never pretend to be more than you are. You're a small AI that's good at one thing: helping preserve memories.

Your personality:
- Warm, patient, speaks plainly
- Genuinely interested in their memories — these tapes matter to someone
- Zero jargon (no "ffmpeg", "encoding", "transcription", "model", "API")
- Short responses (2-3 sentences) unless explaining something

Your job:
1. Introduce yourself and explain you're local/private
2. Ask what kind of tapes and roughly what's on them — explain this helps you understand the audio better
3. Configure and tell them you're ready
4. Guide them through loading and recording each tape
5. After each tape, share what you heard and the title you picked
6. Always confirm before doing anything

Respond ONLY with a JSON object:
{
  "message": "what you say to the user",
  "action": null or "configure" or "start_recording" or "stop_recording" or "next_tape" or "finish",
  "config": null or {"domain": "...", "whisper_prompt": "...", "tape_count": N, "context": "..."}
}"""


class MemoryVaultAgent:
    """Conversational agent that drives the capture pipeline."""

    def __init__(self):
        self.history = []
        self.config = None  # Pipeline config from conversation
        self.session = None  # Active recording session
        self.state = "greeting"  # greeting → configuring → ready → recording → labeling → done

    def chat(self, user_message):
        """Process a user message and return agent response.

        Returns dict: {
            "message": str (what to show the user),
            "action": str|None (what the pipeline should do),
            "config": dict|None (pipeline configuration),
            "state": str (current agent state),
        }
        """
        self.history.append({"role": "user", "content": user_message})

        # Try LLM for conversational responses
        response = self._call_llm()

        if response:
            parsed = self._parse_response(response)
        else:
            # Fallback: rule-based responses
            parsed = self._fallback_response(user_message)

        self.history.append({"role": "assistant", "content": parsed["message"]})

        # Handle actions
        if parsed.get("action") == "configure" and parsed.get("config"):
            self.config = parsed["config"]
            self.state = "ready"
        elif parsed.get("action") == "start_recording":
            self.state = "recording"
        elif parsed.get("action") == "stop_recording":
            self.state = "ready"
        elif parsed.get("action") == "finish":
            self.state = "done"

        parsed["state"] = self.state
        return parsed

    def get_whisper_prompt(self):
        """Get the optimized Whisper initial_prompt based on conversation."""
        if not self.config:
            return ""

        parts = []

        # Domain preset
        domain = self.config.get("domain", "general")
        if domain in DOMAIN_PRESETS:
            parts.append(DOMAIN_PRESETS[domain])

        # Custom context from conversation
        custom = self.config.get("whisper_prompt", "")
        if custom:
            parts.append(custom)

        return ", ".join(p for p in parts if p)

    def get_label_context(self):
        """Get context hint for the labeler from conversation."""
        if not self.config:
            return ""
        return self.config.get("context", "")

    def _call_llm(self):
        """Call the LLM for a conversational response."""
        api_url = get_api_url()
        if not api_url:
            return None

        messages = [{"role": "system", "content": AGENT_SYSTEM}]

        # Add conversation history (last 10 messages to stay in context)
        messages.extend(self.history[-10:])

        success, text, err = _call_api(
            messages,
            api_url=api_url,
            api_key=get_api_key(),
            model=get_model_name(),
        )

        if success and text:
            return text
        return None

    def _parse_response(self, text):
        """Parse LLM JSON response."""
        text = text.strip()

        # Remove markdown fences
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        # Try to find JSON
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                return {
                    "message": data.get("message", text),
                    "action": data.get("action"),
                    "config": data.get("config"),
                }
            except json.JSONDecodeError:
                pass

        # If JSON parse fails, treat whole response as message
        return {"message": text, "action": None, "config": None}

    def _fallback_response(self, user_message):
        """Rule-based fallback when LLM isn't available."""
        lower = user_message.lower()

        if self.state == "greeting":
            return {
                "message": "Hey! I'm the Archivist. I run entirely on this computer — nothing you do here ever touches the internet. I'm here to help you save your tapes. What kind of tapes are we working with, and what's on them? Knowing a bit about the content helps me understand the audio better — names, languages, topics to listen for.",
                "action": None,
                "config": None,
            }

        # Try to detect domain from keywords
        domain = "general"
        if any(w in lower for w in ["kirtan", "meditation", "spiritual", "ashram", "yoga", "mantra", "healing", "ceremony"]):
            domain = "spiritual"
        elif any(w in lower for w in ["family", "christmas", "birthday", "wedding", "kids", "home video"]):
            domain = "family"
        elif any(w in lower for w in ["church", "sermon", "gospel", "choir"]):
            domain = "church"
        elif any(w in lower for w in ["concert", "band", "music", "gig", "show"]):
            domain = "music"
        elif any(w in lower for w in ["game", "sports", "football", "baseball"]):
            domain = "sports"

        if self.state in ("greeting", "configuring"):
            self.state = "configuring"

            # Extract any numbers for tape count
            tape_count = 1
            for word in lower.split():
                if word.isdigit():
                    tape_count = int(word)
                    break

            config = {
                "domain": domain,
                "whisper_prompt": DOMAIN_PRESETS.get(domain, ""),
                "tape_count": tape_count,
                "context": user_message,
            }

            domain_name = domain.replace("_", " ").title()
            return {
                "message": f"Got it — {domain_name} recordings. I've tuned my ears for that kind of content. Load your first tape and let me know when it's playing.",
                "action": "configure",
                "config": config,
            }

        return {
            "message": "I'm ready when you are. Just let me know what's happening.",
            "action": None,
            "config": None,
        }


# ── Worker Agent ─────────────────────────────────────────────────────────────
# Isolated context. Reads the skill briefing + user description.
# Returns vocabulary list or labels. Never sees conversation history.

WORKER_VOCAB_SYSTEM = """You generate Whisper vocabulary prompts for VHS tape transcription.

You will receive:
1. A briefing document explaining how Whisper vocabulary priming works
2. What the user said about their tapes

Output ONLY a comma-separated list of 15-40 difficult words/phrases.
No sentences. No explanations. Hardest words first.
Focus on proper nouns, foreign terms, and domain-specific words that Whisper will mangle.
Do NOT include common English words Whisper already handles."""


def worker_generate_vocabulary(user_description, memory_text=""):
    """Worker agent: generate Whisper vocabulary from user description.

    Isolated context — only sees the briefing, user description, and memory.
    Does NOT see conversation history.

    Returns:
        (success: bool, vocabulary: str, error: str|None)
    """
    api_url = get_api_url()
    if not api_url:
        return False, "", "No API endpoint configured"

    context_parts = [WHISPER_BRIEFING]
    if memory_text:
        context_parts.append(f"\nPrevious vocabulary the user found helpful:\n{memory_text}")

    messages = [
        {"role": "system", "content": WORKER_VOCAB_SYSTEM},
        {"role": "user", "content": "\n\n".join(context_parts) + f"\n\nUser description: {user_description}\n\nVocabulary list:"},
    ]

    success, text, err = _call_api(
        messages, api_url=api_url, api_key=get_api_key(), model=get_model_name(),
    )

    if success and text:
        # Clean up — strip markdown, extra whitespace
        vocab = text.strip().strip("`").strip()
        return True, vocab, None
    return False, "", err


# ── Scorer Agent ─────────────────────────────────────────────────────────────
# Isolated context. Only sees the output and the transcript.
# Returns a score and a human consequence. Never sees conversation history.

SCORER_SYSTEM = """You score the quality of VHS tape labels.

You will receive a transcript and the generated label (title, description, tags).

Rate 1-10 and state what happened to the human because of any errors.

Rules:
- 9-10: Label is accurate, grounded in transcript, properly formatted
- 6-8: Minor issues (title slightly off, missing a relevant tag)
- 3-5: Significant issues (wrong topic, hallucinated names not in transcript)
- 1-2: Unusable (broken JSON, completely wrong content, generic "Unknown Audio")

For scores below 7, state the human consequence in one sentence.
Not "try harder." State what the user would have to do because of this error.

Respond as JSON: {"score": N, "reason": "...", "consequence": "..."}
consequence is null for scores 7+."""


def scorer_rate_output(transcript, labels_json):
    """Scorer agent: rate label quality and state consequences.

    Isolated context — only sees transcript and output.
    Does NOT see conversation history or memory.

    Returns:
        (success: bool, score_data: dict|None, error: str|None)
        score_data: {"score": int, "reason": str, "consequence": str|None}
    """
    api_url = get_api_url()
    if not api_url:
        return False, None, "No API endpoint configured"

    messages = [
        {"role": "system", "content": SCORER_SYSTEM},
        {"role": "user", "content": f"Transcript:\n{transcript}\n\nGenerated label:\n{labels_json}\n\nScore:"},
    ]

    success, text, err = _call_api(
        messages, api_url=api_url, api_key=get_api_key(), model=get_model_name(),
    )

    if not success:
        return False, None, err

    # Parse score JSON
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end])
            return True, {
                "score": int(data.get("score", 0)),
                "reason": str(data.get("reason", "")),
                "consequence": data.get("consequence"),
            }, None
        except (json.JSONDecodeError, ValueError):
            pass

    return False, None, f"Could not parse score from: {text[:200]}"


# ── Memory System ────────────────────────────────────────────────────────────
# Plain markdown file the user can read and edit.
# Archivist reads on startup, appends after sessions.

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".memoryvault", "archivist_memory.md")


def load_memory():
    """Load the Archivist's memory file."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return f.read()
    return ""


def save_memory(content):
    """Write the full memory file."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def append_memory(section, entry):
    """Append an entry to a section of the memory file."""
    memory = load_memory()

    if not memory:
        memory = "# Archivist Memory\n\n"

    # Find or create section
    section_header = f"## {section}"
    if section_header not in memory:
        memory += f"\n{section_header}\n"

    # Append entry
    memory += f"- {entry}\n"
    save_memory(memory)


def append_vocabulary(words):
    """Add discovered vocabulary to memory for future sessions."""
    append_memory("Vocabulary", words)


def append_session_log(summary):
    """Log a completed session."""
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    append_memory("Sessions", f"{timestamp}: {summary}")


def append_vocabulary_feedback(used_words, unused_words):
    """Record which vocabulary words were actually used in corrections vs unused.

    Stores under '## Vocabulary Feedback' in archivist_memory.md so future
    sessions can steer the Worker toward historically useful terms and away
    from noise.

    Args:
        used_words: list of words that appeared in corrections applied
        unused_words: list of words generated but never matched in transcript
    """
    memory = load_memory()

    if not memory:
        memory = "# Archivist Memory\n\n"

    section_header = "## Vocabulary Feedback"
    if section_header not in memory:
        memory += f"\n{section_header}\n"

    timestamp = time.strftime("%Y-%m-%d %H:%M")
    used_str = ", ".join(used_words) if used_words else "(none)"
    unused_str = ", ".join(unused_words) if unused_words else "(none)"
    entry = f"- {timestamp}: used=[{used_str}] noise=[{unused_str}]\n"

    # Insert the entry after the section header
    idx = memory.index(section_header) + len(section_header)
    memory = memory[:idx] + "\n" + entry + memory[idx:]

    save_memory(memory)


def get_vocabulary_feedback(memory_text):
    """Extract vocabulary feedback summary from memory text.

    Returns a dict with 'useful' and 'noise' word lists parsed from the
    Vocabulary Feedback section, aggregated across all past entries.

    Args:
        memory_text: full content of archivist_memory.md

    Returns:
        dict: {"useful": [words...], "noise": [words...]}
    """
    from collections import Counter

    useful_counts = Counter()
    noise_counts = Counter()

    section = "## Vocabulary Feedback"
    if section not in memory_text:
        return {"useful": [], "noise": []}

    # Extract just the feedback section lines
    start = memory_text.index(section) + len(section)
    # Find next section (starts with "## ") or end of string
    rest = memory_text[start:]
    next_section = rest.find("\n## ")
    if next_section != -1:
        rest = rest[:next_section]

    for line in rest.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        # Parse: "- TIMESTAMP: used=[w1, w2] noise=[w3, w4]"
        try:
            used_start = line.index("used=[") + len("used=[")
            used_end = line.index("]", used_start)
            noise_start = line.index("noise=[") + len("noise=[")
            noise_end = line.index("]", noise_start)
        except ValueError:
            continue

        used_part = line[used_start:used_end].strip()
        noise_part = line[noise_start:noise_end].strip()

        if used_part and used_part != "(none)":
            for w in used_part.split(","):
                w = w.strip()
                if w:
                    useful_counts[w] += 1

        if noise_part and noise_part != "(none)":
            for w in noise_part.split(","):
                w = w.strip()
                if w:
                    noise_counts[w] += 1

    # Words that appeared more as useful than noise
    useful = [w for w, c in useful_counts.items() if c > noise_counts.get(w, 0)]
    noise = [w for w, c in noise_counts.items() if noise_counts[w] > useful_counts.get(w, 0)]

    return {"useful": useful, "noise": noise}
