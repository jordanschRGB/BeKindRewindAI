# BeKindRewindAI

**A desktop app that digitizes VHS tapes with a local AI assistant. No cloud. No accounts. No internet required.**

Tape conversion services charge $25-50 per tape, take weeks, and produce mediocre results. BeKindRewindAI does it on your own computer, with an AI that actually understands what's on the tape.

> **Status:** Exploration / proof of concept. The capture pipeline works end-to-end on Windows. Hardware testing with physical capture cards is ongoing. The AI layer is functional and tested against real models.

---

## What Makes This Different

Most "AI-powered" tools bolt a chatbot onto an existing workflow and call it innovation. This project takes a different approach: **the AI is useful because it solves a real problem that the workflow couldn't solve without it.**

### The Problem With Tape Digitization

When you digitize a VHS tape, ffmpeg does the heavy lifting — it captures the video signal, encodes it, and saves a file. That part is straightforward. The hard part is everything after:

- **What's on this tape?** You have 20 unlabeled VHS tapes from the 90s. The file names are `tape_001.mp4` through `tape_020.mp4`. Good luck finding Christmas 1995.
- **Is the audio usable?** Whisper (OpenAI's speech recognition) can transcribe the audio, but VHS audio is degraded — muffled speech, background hum, tracking artifacts. Whisper will mangle proper nouns, foreign words, and domain-specific vocabulary.
- **Can AI help with transcription?** This is where it gets interesting.

### How BeKindRewindAI Uses AI Differently

The typical approach would be: capture tape → run Whisper → show transcript. The transcript would be mediocre because Whisper has no context about what it's listening to.

**Our approach:** Before recording, the AI assistant (the Archivist) has a brief conversation with the user:

```
Archivist: "Hey! I'm the Archivist. I run entirely on this computer —
            nothing leaves this machine. What kind of tapes are we
            working with?"

User:      "Kirtan recordings from our ashram in the 90s"

Archivist: "Got it — I've tuned my ears for spiritual recordings.
            I'll listen for Sanskrit terms, mantra names, and
            teacher names. Load the first tape when ready."
```

Behind the scenes, this conversation generates a **vocabulary prompt** that's injected into Whisper's decoder. Instead of Whisper hearing "oh no my shivaya" and transcribing gibberish, it's primed with "Om Namah Shivaya, satsang, kirtan, Anandamayi" — and the transcription accuracy jumps dramatically.

**The AI isn't replacing anything. It's making an existing tool (Whisper) significantly better by gathering context that the tool can't gather itself.** The user thinks they're having a friendly conversation. The system is optimizing a speech recognition pipeline.

After capture, a second AI pass reads the transcript and generates a human-readable title, description, and tags:

```
tape_003.mp4 → "Kirtan with Anandamayi — Om Namah Shivaya (1994).mp4"
```

The user gets named, organized, searchable files instead of a folder of `tape_001` through `tape_020`.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Browser UI (localhost:5000)                     │
│  ┌──────────────────────────────────────────┐   │
│  │  The Archivist (chat interface)           │   │
│  │  Guides users, gathers context,           │   │
│  │  configures pipeline, shows results       │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  Capture Engine (ffmpeg)                  │   │
│  │  Device detection, signal check,          │   │
│  │  auto-stop on silence/black, encode       │   │
│  └──────────────┬───────────────────────────┘   │
│                 │                                │
│  ┌──────────────▼───────────────────────────┐   │
│  │  AI Layer (all local, all optional)       │   │
│  │                                           │   │
│  │  faster-whisper    →  Audio transcription  │   │
│  │  (+ vocabulary      (primed by Archivist  │   │
│  │    from chat)        conversation)         │   │
│  │                                           │   │
│  │  Qwen 3.5 4B      →  Title, description,  │   │
│  │  (via any OpenAI-    tags from transcript  │   │
│  │   compatible API)                          │   │
│  └───────────────────────────────────────────┘   │
│                                                  │
│  JSON API (same server, /api/* endpoints)        │
│  Agents and scripts can drive the full pipeline  │
└─────────────────────────────────────────────────┘
```

### Design Decisions

**Why a local web UI instead of a native app?**
Flask serves a web page to `localhost`. This means the UI works on any OS, looks the same everywhere, and can be accessed from a phone or tablet sitting next to the VCR. The system tray icon launches the browser automatically — the user never thinks about it being a "web app."

**Why faster-whisper instead of the OpenAI API?**
Privacy. VHS tapes contain personal memories — family moments, private ceremonies, children. Sending that audio to a cloud API is a non-starter for many users. faster-whisper runs entirely locally using CTranslate2, with automatic CUDA acceleration if a GPU is available.

**Why is the AI optional?**
The capture pipeline works perfectly without any AI. You get `tape_001.mp4` through `tape_020.mp4` and that's fine. The AI layer is a one-click download (~3GB for both models) that adds transcription and smart labeling. Users who don't want it, or whose hardware can't run it, lose nothing.

**Why Qwen 3.5 4B for labeling?**
It runs on any GPU made after 2018 (4GB+ VRAM), works on CPU as a fallback, and is smart enough to generate accurate titles from noisy transcripts. The labeler connects to any OpenAI-compatible API — LM Studio, Ollama, OpenRouter, or the bundled llama-cpp-python. Users with their own inference setup can point it wherever they want.

**Why does the Archivist introduce itself as local?**
People are justifiably suspicious of AI that asks questions. "What's on your tapes?" sounds like data collection. The Archivist leads with transparency: *"I run entirely on this computer — nothing leaves this machine. Knowing what's on the tapes helps me understand the audio better."* The question has a clear, honest purpose that the user can verify.

---

## The Archivist

The conversational AI agent that drives the app. Not a chatbot — a pipeline controller with a friendly face.

**What it does:**
- Asks about tape content → generates Whisper vocabulary prompts
- Detects domain (family, spiritual, music, sports, church) → applies presets
- Confirms before every action ("Ready to start recording?")
- Reports results after capture ("This sounds like a birthday party — I'm saving it as...")
- Remembers preferences across sessions via a plain `.md` file the user can read and edit

**What it doesn't do:**
- No internet access
- No data collection
- No unsupervised actions
- No pretending to be more than it is

### Three-Agent Design (Planned)

The next iteration separates concerns into three roles running on a single model:

| Agent | Role | Context |
|-------|------|---------|
| **Archivist** | Talks to user, drives pipeline | Conversation history + memory |
| **Scorer** | Rates output quality, states consequences | Only the output + transcript |
| **Worker** | Generates labels as JSON | Only the transcript + last score |

Same model, same weights, different system prompts, isolated context. The Scorer enforces quality without the user seeing it — if the Worker mislabels a tape, the Scorer doesn't say "try harder," it says "your label forced the user to rename the file manually."

---

## Quick Start

### From Source
```bash
cd memoryvault
pip install -r requirements.txt
python main.py
```
Browser opens to `http://localhost:5000`. Click **Chat** to talk to the Archivist, or use the manual **Setup** → **Record** → **Library** workflow.

### Pre-built Binary (Windows)
```bash
cd memoryvault
bash build.sh
# Output: dist/MemoryVault.exe (32MB)
```
Double-click the exe. If ffmpeg isn't installed, the app offers a one-click install.

### AI Features (Optional)
1. Go to **Settings** → **Smart Features**
2. Click **Install** for Whisper (transcription, ~460MB)
3. Configure an LLM endpoint for labeling (LM Studio, Ollama, or OpenRouter)

---

## JSON API

Every feature is accessible via API. Agents, scripts, and other tools can drive the full pipeline programmatically.

```bash
# Check status
curl http://localhost:5000/api/status

# Detect capture devices
curl -X POST http://localhost:5000/api/setup/detect

# Start a 3-tape session
curl -X POST http://localhost:5000/api/session/start \
  -H "Content-Type: application/json" \
  -d '{"tape_count": 3}'

# Signal next tape is loaded
curl -X POST http://localhost:5000/api/session/next

# Chat with the Archivist
curl -X POST http://localhost:5000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "I have 5 VHS tapes from our ashram"}'

# Browse captured tapes
curl http://localhost:5000/api/library
```

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | Python 3.11+, Flask | Simple, portable, everyone knows it |
| Frontend | Vanilla HTML/CSS/JS, custom design | No build step, no node_modules, no framework churn |
| Capture | ffmpeg (bundled or auto-installed) | Industry standard, cross-platform |
| ASR | faster-whisper (CTranslate2) | Local, fast, CUDA-accelerated, no torch dependency |
| Labeling | Any OpenAI-compatible API | Works with LM Studio, Ollama, OpenRouter, llama-cpp-python |
| Packaging | PyInstaller | Single .exe/.app, no Python install required |
| System tray | pystray | Native OS integration |

---

## Project Structure

```
memoryvault/
├── main.py              # Entry point — starts server + tray icon
├── app.py               # Flask app factory
├── api.py               # JSON API endpoints
├── agent.py             # The Archivist — conversational AI agent
├── session.py           # Batch session state machine
├── pipeline.py          # Capture → encode → validate → transcribe → label
├── library.py           # Tape library (list, read, save metadata)
├── engine/
│   ├── devices.py       # Cross-platform device detection (v4l2/avfoundation/dshow)
│   ├── capture.py       # ffmpeg recording with auto-stop
│   ├── encode.py        # MP4 encoding (x264, no HandBrake dependency)
│   ├── validate.py      # Post-capture validation (duration, audio, video checks)
│   ├── transcribe.py    # faster-whisper ASR with vocabulary priming
│   ├── labeler.py       # LLM-powered title/tag generation
│   ├── inference.py     # Model management, hardware detection, download
│   └── deps.py          # Dependency management (ffmpeg auto-install)
├── tray.py              # System tray icon
├── static/              # Custom CSS (warm analog aesthetic), JS
├── templates/           # Flask templates (home, setup, session, library, chat, settings)
├── tests/               # 37 tests covering validation, session, library, API, inference, ASR, labeling
├── memoryvault.spec     # PyInstaller build config
└── build.sh             # One-command build script
```

---

## What This Project Is Really About

There's a distinction nobody talks about: **AI inference and AI agents are not the same thing.**

An inference call is a model generating text. That's it. A function that takes input and returns output. Whisper takes audio and returns text. A labeler takes text and returns JSON. These are tools — powerful, useful, but not magic.

An agent is an inference call **with context and tools.** Same model, same weights — but you give it specific context about the situation and specific tools it can use. The result is completely different, not because the model got smarter, but because you gave it the right information and the right levers.

The Archivist in this project is a 4B parameter model. It's not intelligent. But when you tell it "these are kirtan tapes from an ashram," it takes that context and injects domain vocabulary into Whisper's decoder — and suddenly a speech recognition system that was producing garbage starts producing accurate transcripts. The model didn't improve Whisper. The *context* improved Whisper. The model was just the mechanism for gathering that context naturally.

This extends to quality control. The same 4B model, given a different system prompt and isolated context, becomes a scorer that rates output and states consequences: "your label forced the user to rename files manually." It's not anthropomorphizing — these models are trained on agentic patterns. Applying targeted pressure language that penalizes failure isn't giving the model feelings. It's using the training distribution effectively. A score of 2/10 with a concrete consequence adjusts the next output more reliably than a paragraph of instructions.

The three-agent design in this project (Archivist, Scorer, Worker) isn't three AIs. It's one model called three times with different context and different tools. The architecture is the intelligence. The model is just the engine.

If you're building AI products: the model matters less than you think. The context you give it, the tools you connect, and how you decompose the task into clear roles — that's what determines whether it works or doesn't.

---

## License

MIT

---

*Built with Claude Code. The Archivist runs on Qwen 3.5 4B.*
