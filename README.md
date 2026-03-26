# BeKindRewindAI

A desktop app that digitizes VHS tapes with a local AI assistant. Nothing leaves your computer.

> Proof of concept. Capture pipeline works on Windows. AI tested against real models. Hardware testing ongoing.

---

## The Problem

You have 20 unlabeled VHS tapes. You digitize them. Now you have 20 files named `tape_001.mp4` through `tape_020.mp4`. Good luck finding Christmas 1995.

Speech recognition (Whisper) can transcribe the audio, but VHS audio is degraded. Whisper mangles proper nouns, foreign words, and anything unusual. "Om Namah Shivaya" becomes "oh no my shivaya."

## The Approach

The user says what's on their tapes. The system generates a vocabulary list — `Om Namah Shivaya, satsang, kirtan, Anandamayi` — and injects it into Whisper's decoder. Transcription accuracy jumps because Whisper now expects those words.

After capture, a labeling pass generates a title: `tape_003.mp4` becomes `Kirtan with Anandamayi — Om Namah Shivaya (1994).mp4`.

Then a review pass — the Dreamer — quietly checks the transcript against known vocabulary, flagging anything that looks like a speech recognition mishear. Corrections are applied deterministically, not generated.

The system gets smarter with each tape. Vocabulary accumulates in a plain `.md` file. Tape 20 has dramatically better transcription than tape 1 — same model, richer input.

---

## Why Multi-Agent Pipelines Usually Get Worse

Everyone knows how agents work. Nobody talks about why chaining them usually produces worse output than a single call.

Every pass through a model is a lossy compression. Detail is lost. Output trends toward generic. "Anandamayi Ma leading kirtan at the Ashland ashram in 1994" becomes "Spiritual Chanting Session" after enough passes. The specific details — the name, the place, the year — compress away first because they're the least common tokens.

This is why "AI improves AI output" pipelines degrade. Each step inherits and amplifies the previous step's errors. A correction agent that rewrites a transcript can only compress — it can't add information it doesn't have. It confidently "fixes" correct words into wrong ones.

**The rule this project follows: every agent step must convert information from one type to another. If input and output are the same type, the step can only compress toward the mean. Delete it.**

The one exception: a validator that outputs a binary signal (good/bad) or doubt signals (the Dreamer pattern). That's a useful compression — from a full document to a flag. It can't make things worse because it doesn't change anything.

## What an Agent Actually Is

An agent is: **model + identity + context + tools.**

Everything else is plumbing. Same model, same weights — different identity and context produce fundamentally different behavior. This project uses one model (Qwen 3.5 4B) in three roles:

| Agent | Identity | Context | Tools | Output type |
|-------|----------|---------|-------|-------------|
| **Archivist** | Warm, transparent, drives pipeline | Conversation + memory | All six | Decisions + user-facing text |
| **Worker** | Structured output only | Skill briefing + transcript | None (output IS the result) | Vocabulary lists, title/tags JSON |
| **Dreamer** | Reflective, low-confidence, noticing | Transcript + known vocabulary | One: log observation | Doubt signals |

### Why Three Roles Instead of One

Not because the model can't do all three. Because **context isolation prevents bleed.** The Archivist's warm tone shouldn't influence vocabulary generation. The Dreamer's doubt mode shouldn't affect labeling confidence. Separate calls with separate system prompts produce measurably different outputs — we tested this.

The Dreamer caught 3/3 mangled Sanskrit terms in testing. The same model with a task-oriented prompt ("check for errors") caught 2/3. A generic prompt ("review this") wrote an essay instead of JSON. The identity in the prompt steers the output distribution. It's not vibes — it's mechanical.

### The Design Rule

Every agent delegation must be a **conversion of information from one type to another.** If input and output are the same type, the model can only compress — it trends toward generic, losing the specific details that matter.

| Step | In | Out | Type change? | Justified? |
|------|-----|------|-------------|------------|
| Vocabulary | Natural language | Decoder token list | Yes — expansion from seed | Yes |
| Whisper | Audio waveform | Text | Yes — modality change | Yes |
| Labeling | Paragraphs of transcript | Title + tags | Yes — compression to summary | Yes |
| Dreamer | Transcript + vocabulary | Doubt signals | Yes — cross-reference check | Yes |
| Correction agent | Text → "better" text | Same type | No | **No — this degrades quality** |

If you're asking a model to improve its own output in the same format, stop. That compresses toward the mean. Use a validator (pass/fail) or a different-mode reviewer (the Dreamer), not a corrector.

### Memory

`~/.memoryvault/archivist_memory.md` — plain markdown. Stores vocabulary that worked, user preferences, confirmed corrections, session history. The user can open it in Notepad.

The memory loop: each tape's vocabulary feeds the next tape's Whisper priming. The system improves at the input, not by patching outputs.

---

## The Pipeline

```
Record tape (ffmpeg, no AI)
       ↓
Validate recording (gigabytes → yes/no)
       ↓
Transcribe (Whisper, primed with MEMORY.md vocabulary)
       ↓
Dreamer reviews (transcript + vocabulary → doubt signals)
       ↓
Archivist applies corrections (only where doubt + memory align, deterministic)
       ↓
Label (transcript → title + tags)
       ↓
Save metadata. Update MEMORY.md with new vocabulary.
       ↓
Next tape (now with richer vocabulary).
```

Harness controls flow. Model fills in blanks. No step refines another step's output. Memory accumulates at the edges.

---

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Browser opens to `http://localhost:5000`.

**AI features** require an OpenAI-compatible endpoint (LM Studio, Ollama, or OpenRouter). Configure in **Settings**.

**Pre-built binary:** `bash build.sh` produces a 32MB `.exe`.

**CLI mode:** `python harness/runner.py` for the direct pipeline without the web UI.

---

## Tech Stack & Credits

| Component | Project | License |
|-----------|---------|---------|
| Agent harness | [Nanobot](https://github.com/HKUDS/nanobot) (HKUDS) | MIT |
| Agent loop (demo) | [smolagents](https://github.com/huggingface/smolagents) (HuggingFace) | Apache 2.0 |
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (SYSTRAN) | MIT |
| LLM inference | [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) | MIT |
| LLM model | [Qwen 3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B) (Qwen Team) | Apache 2.0 |
| Video capture | [ffmpeg](https://ffmpeg.org/) | LGPL/GPL |
| Web framework | [Flask](https://flask.palletsprojects.com/) | BSD |
| Packaging | [PyInstaller](https://pyinstaller.org/) | GPL |

### Architectural Influences

- [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) — Zero-trust agent runtime. Tool allowlists and the "physically impossible, not just discouraged" philosophy.
- [OpenClaw](https://github.com/openclaw) — Multi-agent orchestration. The Archivist/Worker/Dreamer separation descends from the Natasha/Scout/Skeptic pattern.
- [Claude Code](https://claude.ai/code) (Anthropic) — This project was built in a single session.

---

## Project Structure

```
├── main.py              # Entry point (Flask + system tray)
├── app.py               # Flask app factory
├── api.py               # JSON API + chat endpoint
├── agent.py             # Three agents: Archivist, Worker, Dreamer
├── SOUL.md              # Archivist identity and behavior
├── AGENTS.md            # Agent architecture documentation
├── harness/
│   ├── tools.py         # 6 constrained tools (no shell, no delete, no network)
│   └── runner.py        # Deterministic pipeline (harness controls flow)
├── orchestrator.py      # smolagents demo (model controls flow)
├── engine/
│   ├── devices.py       # Cross-platform capture card detection
│   ├── capture.py       # ffmpeg recording with auto-stop
│   ├── encode.py        # MP4 encoding (x264)
│   ├── validate.py      # Post-capture file validation
│   ├── transcribe.py    # faster-whisper with vocabulary priming
│   ├── labeler.py       # LLM title/tag generation
│   ├── inference.py     # Model management + hardware detection
│   └── deps.py          # Auto-install ffmpeg
├── skills/
│   └── whisper_briefing.md  # Worker reads this before vocabulary tasks
├── tests/               # 37 tests
└── docs/
    └── architecture.html    # Visual architecture diagram
```

---

## License

MIT

---

*Built with [Claude Code](https://claude.ai/code). The Archivist runs on [Qwen 3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B).*
