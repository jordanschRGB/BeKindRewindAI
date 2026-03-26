# BeKindRewindAI

A desktop app that digitizes VHS tapes with a local AI assistant. Nothing leaves your computer.

> Proof of concept. Capture pipeline works on Windows. AI tested against real models. Hardware testing ongoing.

---

## The Problem

You have 20 unlabeled VHS tapes. You digitize them. Now you have 20 files named `tape_001.mp4` through `tape_020.mp4`. Good luck finding Christmas 1995.

Speech recognition (Whisper) can transcribe the audio, but VHS audio is degraded. Whisper mangles proper nouns, foreign words, and anything unusual. "Om Namah Shivaya" becomes "oh no my shivaya."

## The Approach

Before recording, the Archivist (a local AI assistant) asks: *"What kind of tapes are we working with?"*

The user says: *"Kirtan recordings from our ashram."*

Behind the scenes, this generates a vocabulary list — `Om Namah Shivaya, satsang, kirtan, Anandamayi` — that gets injected into Whisper's decoder. Transcription accuracy jumps because Whisper now expects those words.

After capture, a second pass generates a title: `tape_003.mp4` becomes `Kirtan with Anandamayi — Om Namah Shivaya (1994).mp4`.

The user has a conversation. The system optimizes a speech recognition pipeline.

---

## Three Agents, One Model

The system uses one model (Qwen 3.5 4B, ~2.5GB) called three times with different prompts and isolated context:

| Agent | Job | Sees |
|-------|-----|------|
| **Archivist** | Talks to user, drives pipeline | Conversation + memory |
| **Worker** | Generates vocabulary lists and labels | Skill briefing + transcript only |
| **Scorer** | Rates output quality 1-10 | Output + transcript only |

The Scorer doesn't say "try harder." It says: *"Your label 'Unknown Audio' forced the user to listen to the whole tape again and rename it themselves. That took 45 minutes."*

One concrete consequence adjusts the next output more reliably than a paragraph of instructions. Too much breaks small models — they collapse into apologizing. One statement is the right calibration.

### Why Task Delegation Matters

Asking a single model to do everything — chat with the user, transcribe, label, and judge its own output — produces worse results than splitting those into isolated roles. Not because the model can't do all four, but because:

- **Context bleed:** The model's labeling is influenced by the conversation tone. Isolated context prevents this.
- **Self-evaluation fails:** Models don't reliably judge their own output. A separate scoring call with fresh context catches errors the generator missed.
- **Skill briefings work:** The Worker reads a reference document about how Whisper vocabulary priming works before generating vocabulary. This is like handing an employee a procedures manual — it improves output without changing the model.

Each delegation has a purpose. If splitting a task doesn't improve the outcome, don't split it.

### Memory

The Archivist maintains a plain `.md` file at `~/.memoryvault/archivist_memory.md`. It stores vocabulary that worked, user preferences, and session history. The user can open it in Notepad and read or edit anything the Archivist remembers.

No database. No vector store. Full transparency.

---

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Browser opens to `http://localhost:5000`. Click **Chat** to talk to the Archivist.

**AI features** require an OpenAI-compatible endpoint (LM Studio, Ollama, or OpenRouter). Configure in **Settings**.

**Pre-built binary:** `bash build.sh` produces a 32MB `.exe`.

---

## How It Works

```
User → Archivist (chat) → Worker (vocabulary) → Whisper (primed)
                                                       ↓
                                                  transcript
                                                       ↓
                                              Worker (label) → Scorer (rate)
                                                                    ↓
                                                              score < 7? retry
                                                              score ≥ 7? save
```

The agent loop is powered by [smolagents](https://github.com/huggingface/smolagents) — the model decides which tools to call. Ten registered tools handle device detection, capture, encoding, transcription, labeling, scoring, and memory.

---

## Tech Stack & Credits

| Component | Project | Role |
|-----------|---------|------|
| Agent framework | [smolagents](https://github.com/huggingface/smolagents) (HuggingFace, Apache 2.0) | Tool-calling agent loop, logging, step tracking |
| Speech recognition | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (SYSTRAN, MIT) | Local ASR via CTranslate2, CUDA-accelerated |
| LLM inference | [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) (MIT) | Offline GGUF model loading |
| LLM model | [Qwen 3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B) (Qwen Team, Apache 2.0) | Conversation, labeling, scoring |
| Video capture | [ffmpeg](https://ffmpeg.org/) (LGPL/GPL) | Capture, encode, audio extraction |
| Web framework | [Flask](https://flask.palletsprojects.com/) (BSD) | Local server, UI, API |
| Packaging | [PyInstaller](https://pyinstaller.org/) (GPL) | Single-binary distribution |
| System tray | [pystray](https://github.com/moses-palmer/pystray) (LGPL) | Native OS tray icon |
| CSS framework inspiration | [Pico CSS](https://picocss.com/) (MIT) | Dark theme starting point (now custom) |

### Architectural Influences

- [ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw) — Zero-trust agent runtime. Informed the permission model and tool gating philosophy.
- [OpenClaw](https://github.com/openclaw) — Multi-agent orchestration patterns. The Archivist/Worker/Scorer separation mirrors the Natasha/Scout/Skeptic architecture.
- [Claude Code](https://claude.ai/code) (Anthropic) — Development environment. This project was built in a single session using Claude Code's subagent-driven development workflow.

---

## Why This Exists

An agent is just an inference call with context and tools. Same model, same weights — different context produces different behavior.

This project tests that idea with a real use case: one small model, clear roles, isolated context, real tools, and an outcome that's genuinely useful to someone who doesn't care about AI. The interesting part isn't the model — it's how you decompose the task and what context you give each piece.

---

## Project Structure

```
├── main.py              # Entry point
├── app.py               # Flask app
├── api.py               # JSON API
├── agent.py             # Three-agent system (Archivist, Worker, Scorer)
├── orchestrator.py      # smolagents tool-calling loop
├── session.py           # Batch capture state machine
├── pipeline.py          # Capture → encode → validate → transcribe → label
├── library.py           # Tape metadata storage
├── engine/
│   ├── devices.py       # Cross-platform device detection
│   ├── capture.py       # ffmpeg recording with auto-stop
│   ├── encode.py        # MP4 encoding
│   ├── validate.py      # Post-capture file validation
│   ├── transcribe.py    # faster-whisper with vocabulary priming
│   ├── labeler.py       # LLM title/tag generation (API + local fallback)
│   ├── inference.py     # Model management and hardware detection
│   └── deps.py          # Auto-install ffmpeg
├── skills/
│   └── whisper_briefing.md  # Worker reads this before generating vocabulary
├── tests/               # 37 tests
└── docs/
    └── architecture.html    # Interactive architecture diagram
```

---

## License

MIT

---

*Built with [Claude Code](https://claude.ai/code). The Archivist runs on [Qwen 3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B).*
