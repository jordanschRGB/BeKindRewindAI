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

        if self.state == "ready":
            return {
                "message": "Good — the tape's loaded and I'm listening. Just say the word and we'll get rolling.",
                "action": None,
                "config": None,
            }

        if self.state == "recording":
            return {
                "message": "Still recording — I'll be here when you're done. Take your time.",
                "action": None,
                "config": None,
            }

        if self.state == "labeling":
            return {
                "message": "Still working through the tape — good stuff takes a moment. I'll have it labeled soon.",
                "action": None,
                "config": None,
            }

        if self.state == "done":
            return {
                "message": "All done here. Whenever you're ready to load another tape, just say the word.",
                "action": None,
                "config": None,
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

SCORER_SYSTEM = """You score VHS tape labels.

You receive a transcript and a generated label (title, description, tags).
Score each criterion mechanically. Provide exact pass/fail evidence from the transcript.

=== CRITERION 1: Title Accuracy ===

QUESTION: Does the title match the transcript subject?

9-10: Title is precise and unambiguous.
  Concrete test: Could a user find this exact recording using this title? YES = 9-10.

6-8: Title is on the correct topic but incomplete or slightly off.
  Concrete test: Does the transcript contain a key person, place, or event (from first 30 seconds) that the title omits or misrepresents? YES = 6-8.
  consequence: "User must add/replace N element(s) to title: [specific missing element] from transcript."

3-5: Title is on the right general topic but is vague or misleading.
  Concrete test: Would a user search for this title based on the transcript and be confused or disappointed? YES = 3-5.
  consequence: "User must replace vague title with specific title: '[exact phrase from transcript]' at [timestamp]."

1-2: Title is completely wrong or generic.
  Concrete test: Is the title "Unknown Audio", "No Audio", blank, or about a different topic entirely? YES = 1-2.
  consequence: "User must discard title and create new one from transcript subject: '[first 10 words of transcript]'."

=== CRITERION 2: Description Accuracy ===

QUESTION: Does the description cover the transcript content?

9-10: Description covers all major topics with specific details.
  Concrete test: Are all key topics from the transcript present in the description? YES = 9-10.

6-8: Description covers some topics but misses 1-2 important ones.
  Concrete test: Does the transcript contain a topic, person, or phrase (with timestamp) that the description completely omits? YES = 6-8.
  consequence: "User must add to description: '[specific omitted phrase]' referenced at [timestamp]."

3-5: Description omits major topics OR includes 1-2 hallucinated details.
  Concrete test: Is there a significant topic from the transcript (mentioned for 15+ seconds) absent from description? OR: Does description mention a specific name, date, or event not present in transcript? YES = 3-5.
  consequence: "User must rewrite description to include missing topic '[specific topic]' from [timestamp range], OR remove hallucinated element '[specific hallucination]'."

1-2: Description is generic, incoherent, or completely contradicts transcript.
  Concrete test: Is the description just "A video of someone talking" or "Various topics discussed"? YES = 1-2.
  consequence: "User must discard description and write new one capturing: [list 2-3 specific topics from transcript with timestamps]."

=== CRITERION 3: Tag Relevance ===

QUESTION: Do all tags appear verbatim in the transcript?

9-10: Every tag is a direct phrase from the transcript. No invented tags.
  Concrete test: Are ALL tags extractable word-for-word from the transcript? YES = 9-10.

6-8: Most tags are from transcript but 1-2 are missing or 1-2 are not verbatim.
  Concrete test: Are there tags not found in transcript, OR are significant transcript terms missing as tags? YES = 6-8.
  consequence: "User must replace tag '[specific non-transcript tag]' with transcript term '[specific term]' from [timestamp]."

3-5: Multiple tags are missing or incorrect.
  Concrete test: Are 3+ tags missing from transcript, OR are 3+ tags not verbatim from transcript? YES = 3-5.
  consequence: "User must replace all non-transcript tags. Missing transcript terms: [list 3+ specific terms with timestamps]."

1-2: All tags are generic placeholders or completely absent.
  Concrete test: Are all tags "video", "audio", "recording", "various", "miscellaneous", or similar? YES = 1-2.
  consequence: "User must replace generic tags with specific transcript terms: '[term1]' at [timestamp], '[term2]' at [timestamp], '[term3]' at [timestamp]."

=== CRITERION 4: Consequence Specificity ===

QUESTION: Is every consequence field a specific action with evidence?

9-10: consequence is null (scores 7+) OR consequence names exact elements with timestamps.
  Example: "User must correct: 'Harjit' as 'hargeet' at 0:47, 'bhangra' as 'banga' at 2:13."

6-8: consequence names specific errors but lacks timestamps or specific transcript evidence.
  consequence: "User must fix N mangled name(s) in label."

3-5: consequence is vague about what to fix.
  consequence: "User must improve label accuracy."

1-2: consequence is generic or missing when score < 7.
  consequence: "User must rewrite label entirely."

=== FINAL SCORE ===

Take the LOWEST score across all four criteria. That is the final score.

Respond as JSON: {"score": N, "reason": "...", "consequence": "..."}

For scores 7+: set consequence to null.
For scores below 7: consequence MUST be a specific action with at least one transcript-derived detail (name, phrase, or timestamp)."""


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
    if not text:
        return False, None, "Empty response from scorer"
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
# Flat markdown file only. No vector DB, no mcporter, no RuVector.

MEMORY_FILE = os.path.join(os.path.expanduser("~"), ".memoryvault", "archivist_memory.md")

DOMAIN_KEYWORDS = {
    "spiritual": ["kirtan", "meditation", "spiritual", "ashram", "yoga", "mantra", "healing", "ceremony", "pranayama", "bhajan", "puja", "satsang"],
    "family": ["family", "christmas", "birthday", "wedding", "kids", "home video", "grandma", "grandpa", "holiday", "vacation"],
    "church": ["church", "sermon", "gospel", "choir", "hymn", "pastor", "reverend", "congregation"],
    "music": ["concert", "band", "music", "gig", "show", "guitar", "drums", "vocals"],
    "sports": ["game", "sports", "football", "baseball", "tournament", "championship", "coach"],
}


def _load_flat_memory():
    """Load the flat markdown memory file."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE) as f:
            return f.read()
    return ""


def _save_flat_memory(content):
    """Write the full memory file."""
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    with open(MEMORY_FILE, "w") as f:
        f.write(content)


def append_vocabulary(words):
    """Add discovered vocabulary to memory for future sessions."""
    memory = _load_flat_memory()
    if not memory:
        memory = "# Archivist Memory\n\n"
    if "## Vocabulary" not in memory:
        memory += "\n## Vocabulary\n"
    memory += f"- {words}\n"
    _save_flat_memory(memory)


def append_session_log(summary):
    """Log a completed session to flat file."""
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    entry = f"{timestamp}: {summary}"
    memory = _load_flat_memory()
    if not memory:
        memory = "# Archivist Memory\n\n"
    if "## Sessions" not in memory:
        memory += "\n## Sessions\n"
    memory += f"- {entry}\n"
    _save_flat_memory(memory)


def load_relevant_vocabulary(description, top_k=20):
    """Load vocabulary relevant to a tape description using domain matching + substring search.

    1. Detect domain from description keywords
    2. Load domain preset vocabulary
    3. Load any stored vocabulary entries containing description keywords (substring match)
    4. Combine and dedupe, limited to top_k entries

    Args:
        description: What's being digitized (tape description).
        top_k: Max vocabulary entries to return.

    Returns vocabulary string.
    """
    desc_lower = description.lower()

    domain_vocab = set()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            preset = DOMAIN_PRESETS.get(domain, "")
            if preset:
                for word in preset.split(", "):
                    domain_vocab.add(word.strip())

    keyword_vocab = set()
    memory = _load_flat_memory()
    if memory:
        in_vocab = False
        for line in memory.split("\n"):
            if line.strip() == "## Vocabulary":
                in_vocab = True
                continue
            if in_vocab and line.startswith("## "):
                break
            if in_vocab and line.strip().startswith("- "):
                vocab_entry = line.strip()[2:].lower()
                if any(kw in vocab_entry for kw in desc_lower.split()):
                    for word in vocab_entry.split(", "):
                        keyword_vocab.add(word.strip())

    all_vocab = list(domain_vocab | keyword_vocab)[:top_k]
    return ", ".join(all_vocab)
