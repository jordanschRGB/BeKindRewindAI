# FIXES.md

**Author:** Forge
**Branch:** feat/vocabulary-feedback-loop
**Date:** 2026-03-25

Summary of every change made in response to CODEBASE_REVIEW.md and the vocab PR round 2 review.

---

## CRITICAL Fixes

### 1. Recorder constructor mismatch (pipeline.py, orchestrator.py)

**Problem:** Both callers passed `(video_cfg, audio_cfg, raw_path)` to `Recorder` which takes `(cmd: list, raw_path: str)`. TypeError on every recording attempt.

**Fix:**
- `pipeline.py`: Added `_build_capture_cmd` to the import line. Inserted `cmd = _build_capture_cmd(config["video"], config["audio"], raw_path)` before `Recorder(cmd, raw_path)`.
- `orchestrator.py`: Same pattern — imported `_build_capture_cmd` locally inside `start_capture`, built the command first, then passed it to `Recorder`.

**Files:** `pipeline.py`, `orchestrator.py`

---

### 2. Nanobot import broken (harness/runner.py, harness/tools.py)

**Problem:** Both files imported from `nanobot.agent.tools.*` — a submodule that does not exist in the `nanobot` PyPI package (v0.x is a robotics framework). `ModuleNotFoundError` on import.

**Fix:** Created `harness/registry.py` with a local `Tool` abstract base class and `ToolRegistry`. Updated both files to import from `harness.registry` instead. No external `nanobot` dependency required.

**Files:** `harness/registry.py` (new), `harness/runner.py`, `harness/tools.py`

---

### 3. requirements.txt — missing dependencies

**Problem:** `requirements.txt` only listed `flask`, `pystray`, `Pillow`. Missing `faster-whisper`, `smolagents`, `llama-cpp-python`. `nanobot` was listed in no pinned form and the PyPI package is wrong.

**Fix:** Added `faster-whisper>=1.0.0`, `smolagents>=1.0.0`, `llama-cpp-python>=0.2.0` with a comment explaining the nanobot situation and pointing to `harness/registry.py`.

**Files:** `requirements.txt`

---

## Non-Critical Fixes

### 4. Model filename mismatch (engine/inference.py)

**Problem:** `qwen-labeler` entry had `filename: Qwen3.5-4B-Q4_K_S.gguf` but the download URL points to `Q4_K_M.gguf`. `is_model_downloaded()` would return `False` after a successful download. Same mismatch in `local_path`.

**Fix:** Changed `filename` and `local_path` to `Q4_K_M.gguf` everywhere in the registry entry. URL unchanged.

**Files:** `engine/inference.py`

---

### 5. Path traversal in /api/library/<tape_id> (library.py)

**Problem:** `get_tape()` joined `tape_id` from URL directly into a filesystem path with no validation. `../../etc/passwd` style traversal would resolve outside the output directory.

**Fix:** Added `os.path.abspath` + `startswith` check identical to `_safe_path()` in `harness/tools.py`. Returns `None` (caller returns 404) on any path that escapes `output_dir`.

**Files:** `library.py`

---

### 6. SaveMetadataTool overwrite (harness/tools.py)

**Problem:** Tool description says "Cannot overwrite existing files" but `open(path, "w")` overwrites unconditionally. The LLM reads the description to decide whether to use the tool — false claim about safety.

**Fix:** Added `if os.path.exists(path): return error` before the write. Description now matches behavior.

**Files:** `harness/tools.py`

---

### 7. GenerateVocabularyTool was a stub (harness/tools.py)

**Problem:** `execute()` just concatenated `existing_vocabulary` with `"(Generate vocabulary for: ...)"` and returned it as vocabulary. Registered tool that returns garbage.

**Fix:** Replaced stub with a real implementation that calls `worker_generate_vocabulary()` from `agent.py`. Falls back to `existing_vocabulary` if the LLM call fails.

**Files:** `harness/tools.py`

---

### 8. Whisper model reloaded on every transcription call (harness/runner.py, harness/tools.py, orchestrator.py)

**Problem:** All three locations instantiated `WhisperModel("small", ...)` directly instead of using the `get_whisper_model()` cache in `engine/transcribe.py`. Loading Whisper small from disk on every tape (5-10 seconds, ~1GB RAM per load).

**Fix:** Replaced all three inline `WhisperModel(...)` instantiations with `from engine.transcribe import get_whisper_model; model = get_whisper_model()`. Model is cached at module level in `transcribe.py` and reused across calls.

**Files:** `harness/runner.py`, `harness/tools.py`, `orchestrator.py`

---

## Vocab PR Round 2 Fixes

### 9. worker_generate_vocabulary dumps full memory_text (agent.py)

**Problem:** `agent.py::worker_generate_vocabulary` passed the full `memory_text` (entire `archivist_memory.md` — sessions, feedback, all vocabulary) to the Worker. The `runner.py` fix (distilled feedback) never propagated back to `agent.py`. On session 20, the 4B model received unboundedly growing context.

**Fix:** Rewrote the function to call `get_vocabulary_feedback(memory_text)` and pass only 2 guidance lines (useful terms / noise terms) rather than the raw memory file. Matches the `runner.py` pattern.

**Files:** `agent.py`

---

### 10. Dead _extract_vocabulary_section function (harness/runner.py)

**Problem:** `_extract_vocabulary_section()` existed in `runner.py` but was never called there (the distilled feedback approach replaced it). Dead code.

**Fix:** Removed the function entirely.

**Files:** `harness/runner.py`

---

## Test Updates

### 11. test_inference.py — test_qwen_found_via_local_path

**Problem:** Test assumed LM Studio was installed with a model at a specific path. Was already failing on CI/dev machines without LM Studio. Also tested against the old `Q4_K_S` filename.

**Fix:** Rewrote to use `monkeypatch` + `tmp_path` — creates a fake model file and patches the registry to point to it. Tests the actual `is_model_downloaded()` logic, not filesystem presence. Updated `test_download_status` to check that the path contains `Q4_K_M` (the correct quantization).

**Files:** `tests/test_inference.py`

---

## New Files

| File | Purpose |
|------|---------|
| `harness/registry.py` | Local `Tool` base class and `ToolRegistry` — replaces nanobot.agent dependency |
| `FIXES.md` | This file |

---

## Test Results

```
56 passed in 3.42s (excluding test_api.py which requires flask installation)
```

All 56 tests passing on feat/vocabulary-feedback-loop after these changes.
