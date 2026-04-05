# SPEC: Minimal Semantic Archive — MXBAI/NPU

## Status

Feature spec. Not yet implemented.

---

## 1. Embedding Pipeline

### MXBAI Integration

**How to call MXBAI embeddings from Python:**

MXBAI models on Rock5B NPU are ONNX-format models run via `onnxruntime` with the Rockchip NPU execution provider (`EP`).

```python
import numpy as np
import onnxruntime as ort

class MXBAIEmbedder:
    def __init__(self, model_path: str):
        providers = [
            ("RockchipNPUExecutionProvider", {"device": "NPU"}),
            "CPUExecutionProvider",
        ]
        self.sess = ort.InferenceSession(model_path, providers=providers)

    def embed(self, text: str) -> np.ndarray:
        # MXBAI models take token IDs; tokenizer must accompany the model
        # Tokenize, run inference, return pooled embedding (dim 1024 or 768)
        ...
```

**Recommendation:** Ship the ONNX model file alongside the code in `~/.memoryvault/models/mxbai-embed-v1.onnx`. Require the user to place it there, or add a one-shot download script. No automatic model fetching.

**If `mxtoolkit` is available** (mxtoolkit/rk_llama), prefer it — it handles tokenization + inference + pooling in one call.

### What to Embed Per Tape

Combine these fields into a single text string, joined with newlines:

```
Title: {title}
Description: {description}
Tags: {tags joined by comma}
Transcript: {transcript (first 2000 chars to avoid context overflow)}
Corrections: {corrections from scorer if present}
```

The combined string is embedded as ONE vector. This captures semantic content in a single shot without multi-vector strategies.

**Embedding on-demand vs batch:**
- **On-demand**: When a new tape finishes labeling, embed it immediately and write to store. Low latency, simple.
- **Batch**: Accumulate new embeddings in memory, flush periodically. Reduces I/O but adds complexity.
- **Recommendation**: On-demand. Simpler, and the NPU handles individual inference requests fine.

### When to Embed New Tapes

In `pipeline.py`'s `_pipeline_thread()`, after `save_metadata()` at the end of AI post-processing (line ~141). The tape metadata is complete at that point (transcript + labels both present).

---

## 2. Storage Layer

**Recommended: SQLite + numpy**

Single file: `~/.memoryvault/semantic_archive.db`

Schema:

```sql
CREATE TABLE tapes (
    id          TEXT PRIMARY KEY,   -- basename of the .json file (no extension)
    metadata_path TEXT NOT NULL,     -- absolute path to the .json sidecar
    embedding   BLOB NOT NULL,       -- numpy array as binary blob
    created_at  TEXT NOT NULL       -- ISO timestamp
);

CREATE INDEX idx_tapes_id ON tapes(id);
```

This is:
- **Zero dependency beyond stdlib + numpy** (sqlite3 is in Python's stdlib)
- **Single file** — easy to back up, easy to nuke and rebuild
- **Idempotent rebuild** — DROP + recreate on re-run
- **No separate service** — everything in-process

**Reject alternatives:**
- `.npy files per tape` — filesystem clutter, no index, harder to query across all
- `JSON manifest + mmap` — over-engineered for this use case
- `Chroma / Qdrant` — separate server process, violates "no separate service"

---

## 3. Lookup Function

```python
from engine.semantic import find_similar_tapes, embed_tape, init_archive

def find_similar_tapes(
    query: str,
    top_k: int = 3,
    archive_path: str = "~/.memoryvault/semantic_archive.db"
) -> list[dict]:
    """
    Find tapes similar to the given query.

    1. Embed query via MXBAI.
    2. Load all tape embeddings from SQLite store.
    3. Compute cosine similarity: (q · v) / (||q|| ||v||)
    4. Return top_k tape metadata dicts (full .json content).

    Returns empty list if no archive exists or query embedding fails.
    """
```

**Return value:** A list of tape metadata dicts (the full JSON from the sidecar file), sorted by similarity descending.

**Cosine similarity implementation:** Pure numpy, no sklearn needed.

```python
def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)
```

---

## 4. Integration Points

### `agent.py`

Add a new function `find_similar_tapes_for_description(description: str) -> list[dict]`.

Call it inside `worker_generate_vocabulary()` to prepend similar tape context to the LLM prompt:

```python
def worker_generate_vocabulary(user_description, memory_text=""):
    # ... existing context building ...

    # NEW: inject similar tape context
    similar = find_similar_tapes_for_description(user_description)
    if similar:
        context_parts.append(_format_similar_tapes_for_prompt(similar))

    # ... rest unchanged ...
```

The `_format_similar_tapes_for_prompt` helper formats the top-2 most similar tapes as:
```
Similar past tapes for context:
1. "{title}": "{transcript excerpt (500 chars)}"
2. "{title}": "{transcript excerpt (500 chars)}"
```

This gives the vocabulary worker relevant historical context without flooding context.

### `pipeline.py`

In `_pipeline_thread()`, after line ~141 (`save_metadata(..., metadata)`):

```python
# Embed this tape for semantic search
try:
    from engine.semantic import embed_tape
    embed_tape(output_dir, base_name, metadata)
except Exception as e:
    logger.warning("Failed to embed tape: %s", e)
```

This runs at session end, after labels + transcript are finalized.

### New file: `engine/semantic.py`

Core module containing:
- `MXBAIEmbedder` class (loads ONNX, runs inference)
- `init_archive(archive_path)` — creates SQLite table if not exists
- `embed_tape(output_dir, base_name, metadata)` — extracts text, embeds, stores in SQLite
- `find_similar_tapes(query, top_k)` — query the archive
- `_get_embedder()` — lazy singleton; loads model once

### New file: `scripts/rebuild_semantic_index.py`

One-shot script:
```bash
python -m scripts.rebuild_semantic_index --output-dir /path/to/tapes
```

Behavior:
1. Walk all `.json` files in `output_dir`.
2. Load each metadata dict.
3. Call `init_archive()` (DROPs existing table first — idempotent).
4. Call `embed_tape()` for each.
5. Report count of indexed tapes.

Run at any time to rebuild from scratch. Safe to re-run.

---

## 5. Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `engine/semantic.py` | **CREATE** | MXBAI embedder + SQLite store + `find_similar_tapes()` |
| `scripts/rebuild_semantic_index.py` | **CREATE** | Idempotent one-shot index rebuild |
| `agent.py` | **MODIFY** | Call `find_similar_tapes_for_description()` in `worker_generate_vocabulary()` |
| `pipeline.py` | **MODIFY** | Call `embed_tape()` after AI post-processing completes |
| `AGENTS.md` | **MODIFY** | Document `engine/semantic.py` as a new integration point |

---

## 6. Exact `find_similar_tapes` Signature

```python
def find_similar_tapes(
    query: str,
    top_k: int = 3,
    archive_path: str | None = None,
) -> list[dict]:
    """
    Find the top-k most similar tapes to the query.

    Args:
        query: Free-text description (e.g. "wedding ceremony in Sanskrit")
        top_k: Number of results to return (default 3)
        archive_path: Override default archive path (~/.memoryvault/semantic_archive.db)

    Returns:
        List of tape metadata dicts, sorted by cosine similarity descending.
        Returns empty list if archive is empty, missing, or embedding fails.
    """
```

**Behavior:**
1. If archive does not exist or top_k == 0, return `[]`.
2. Embed `query` via MXBAI. If embedding fails, log warning and return `[]`.
3. Load all `(id, embedding, metadata_path)` rows from SQLite.
4. Compute cosine similarity between query vector and each stored vector.
5. Sort by similarity descending.
6. Load and return the full metadata dicts for the top_k entries.

---

## 7. Error Handling

All semantic archive operations are **best-effort**:
- If MXBAI model is missing or NPU is unavailable → log warning, return empty list / skip embedding
- If SQLite write fails → log warning, continue (metadata JSON is the source of truth)
- If a tape's JSON sidecar is missing at lookup time → skip that row, log warning

The archive is an **augmentation**, not a requirement. The flat markdown memory and JSON sidecars are the authoritative store.

---

## 8. Constraints Compliance

| Constraint | How Met |
|------------|---------|
| Local NPU only, no cloud | MXBAI ONNX model via onnxruntime + Rockchip NPU EP |
| No separate service | SQLite + numpy in-process |
| Minimal | Single `engine/semantic.py` (~150 LOC), one new script |
| Steal langchain's homework | SQLite is what langchain's `SQLiteVector` uses internally |
| Don't break flat markdown memory | Flat `.md` memory untouched; semantic is additive |
| Idempotent rebuild | `rebuild_semantic_index.py` DROP + re-inserts all rows |
