# BeKindRewindAI

A video recording tool that uses cheap generic capture cards to record home video off VHS tapes and audio cassettes. A small local AI model and a lightweight agent harness handle the parts that normally require technical knowledge — ffmpeg, Whisper, file naming and sorting — so the person using it doesn't have to.

Everything runs on your computer. Nothing touches the internet. I hope it doesn't suck.

Somewhere in a closet, there's a box of tapes nobody's watched since Clinton was president. They're not backed up. They're not in the cloud. They're slowly demagnetizing. One day someone will throw them out because nobody has a VCR and the conversion place wants $30 a tape.

Your grandma's 80th birthday is on one of those tapes. Your kid's first steps might be too.

A $15 capture card, this app, and an afternoon is all it takes. You shouldn't need to know what ffmpeg is to keep your memories.

> Proof of concept. Capture pipeline works on Windows. AI tested against real models. Hardware testing with physical capture cards is next.

**The short version:** Each tape teaches the system new words. By tape 20, transcription is dramatically better than tape 1 — same model, richer input. Three agents share one small model with isolated context. The AI has six tools and physically cannot delete files, access the internet, or run shell commands. It's not a chatbot that tells you how to digitize tapes — it actually does it.

---

## The actual problem with multi-agent pipelines

Every pass through a model loses detail. Specific names, dates, places — gone first, because they're the rarest tokens. Two passes and "Anandamayi Ma leading kirtan at the Ashland ashram in 1994" becomes "Spiritual Chanting Session."

Most multi-agent setups make this worse. Agent A generates something. Agent B "improves" it. But B can't add information it doesn't have — it can only smooth toward average. A correction agent that rewrites a transcript produces something more generic than what Whisper gave you. Confidently wrong is worse than roughly right.

The rule here: each step has to convert information from one type to another. Audio to text. Text to title. Transcript to doubt signals. If input and output are the same type, the step compresses toward the mean. Cut it.

The Dreamer works because its output (doubt signals) is a different type than its input (transcript + vocabulary). It can't make things worse because it doesn't change anything — it just flags. The Archivist decides whether to act, and only applies corrections where the doubt matches known vocabulary. Deterministic string replacement, not model generation.

## Agents

An agent is model + identity + context + tools. That's it. Same model, same weights — different identity and context produce different behavior. One model, three roles:

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
