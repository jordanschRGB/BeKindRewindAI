# SPEC: Minimal Semantic Archive with MXBAI/NPU Embeddings

## Status

Feature spec for bead `4319116f-5f88-4e87-8949-d8c556094d29`.

---

## 1. Embedding Function (MXBAI Integration)

### MXBAI Model

MXBAI provides ONNX-optimized embedding models designed for NPU/hardware acceleration.
Rock5B NPU support means running inference on-device, no cloud.

**Integration path:**
```python
# Recommended: mxtoolkit wrapper
from mxtoolkit import MXEmbedding

model = MXEmbedding("mxbai-embed-large-v1", device="npu")  # or "cpu" fallback
vector = model.embed("text to embed")
```

**Alternative: Direct ONNXRuntime**
```python
import onnxruntime as ort
# Load MXBAI ONNX model, run inference on NPU provider
session = ort.InferenceSession("mxbai-embed-large-v1.onnx", providers=["NPUExecutionProvider"])
```

### What to Embed Per Tape

Combine tape artifacts into a single concatenated string, then embed once:

```
{title} [SEP] {description} [SEP] {transcript} [SEP] tags: {tag1, tag2} [SEP] corrections: {correction list}
```

- **title**: short label string (e.g., "Priya's Wedding Highlights")
- **description**: one-sentence description
- **transcript**: full transcript text (truncated at 8k chars if needed for context length)
- **tags**: comma-joined tag list
- **corrections**: formatted list of CORRECTION→FIX pairs from grading (if any)

**Embedding schedule:**
- **On-demand**: New tapes are embedded immediately after labeling (end of pipeline.py's AI post-processing block)
- **Batch**: Index rebuild script handles all existing .json files

---

## 2. Storage Layer — Recommendation: SQLite + numpy

**Why SQLite + numpy over alternatives:**

| Option | Pros | Cons |
|--------|------|------|
| numpy .npy files | Zero dep, one file per tape | Hard to list/search, no metadata |
| **SQLite + numpy** | Single file, tape_id→embedding+metadata_path, zero extra dep (sqlite3 stdlib) | Slightly more complex |
| JSON manifest + mmap | Human-readable | Slow for large archives, no SQL queryability |
| langchain SimpleVectorStore | "Steals their homework" | Extra dependency, overkill |

**SQLite schema:**
```sql
CREATE TABLE IF NOT EXISTS tape_embeddings (
    tape_id TEXT PRIMARY KEY,   -- basename without .json
    embedding BLOB NOT NULL,     -- numpy array as bytes (npy format)
    title TEXT,
    description TEXT,
    embedded_at REAL            -- unix timestamp
);

CREATE TABLE IF NOT EXISTS tape_metadata (
    tape_id TEXT PRIMARY KEY,
    json_path TEXT NOT NULL     -- path to the .json sidecar
);
```

**Storage file location:** `~/.memoryvault/tape_archive.db`

**Embedding blob format:** Store numpy array as bytes using `numpy.tobytes()` / `numpy.frombuffer()`. Shape/dtype stored in separate metadata columns if needed, or infer from model output dimension.

---

## 3. Lookup Function

```python
def find_similar_tapes(tape_description: str, top_k: int = 3) -> list[dict]:
    """Find tapes semantically similar to a description.

    1. Embed the description via MXBAI
    2. Load all stored embeddings from SQLite
    3. Compute cosine similarity
    4. Return top_k tape metadata dicts (full .json content)

    Args:
        tape_description: Free-text description of what to search for.
        top_k: Number of similar tapes to return (default 3).

    Returns:
        List of tape metadata dicts, sorted by similarity descending.
        Returns empty list if no embeddings exist or MXBAI unavailable.
    """
```

**Cosine similarity:**
```python
import numpy as np

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

---

## 4. Integration Points in Existing Codebase

### `agent.py`

**New function to add:**
- `find_similar_tapes()` — exported from new `harness/semantic_archive.py`

**Modified function:**
- `worker_generate_vocabulary()` — prepending similar tape context to the LLM prompt:
  ```python
  # Before calling the LLM, fetch similar tapes
  similar = find_similar_tapes(user_description, top_k=2)
  context_parts = [WHISPER_BRIEFING]
  if similar:
      prior_context = "\n".join(
          f"Previous tape: {t.get('labels',{}).get('title','Unknown')}\n"
          f"Transcript excerpt: {t.get('transcript','')[:500]}\n"
          for t in similar
      )
      context_parts.append(f"\nPrior similar tapes for context:\n{prior_context}")
  if memory_text:
      context_parts.append(f"\nPrevious vocabulary:\n{memory_text}")
  ```

**New import:** `from harness.semantic_archive import find_similar_tapes`

### `pipeline.py`

**Where to embed new tapes:** End of `_pipeline_thread()`, after `save_metadata()` in the AI post-processing block:
```python
# After: save_metadata(output_dir, base_name, metadata)
# Embed this tape for future semantic search
try:
    from harness.semantic_archive import embed_tape
    embed_tape(base_name, metadata)
except Exception:
    logger.exception("Failed to embed tape")
```

### `harness/semantic_archive.py` (new file)

Core module containing:
- `MXBAIEmbedding` class or `embed_text()` function
- `embed_tape(tape_id, metadata)` — extract text from metadata, embed, store in SQLite
- `find_similar_tapes(tape_description, top_k)` — described above
- `rebuild_index(output_dir)` — one-shot script to index all existing .json files
- `is_available()` — check if MXBAI is reachable (NPU or CPU)

### `library.py`

No changes needed — `find_similar_tapes()` reads `.json` files via the stored `json_path` in the SQLite metadata table.

---

## 5. Files to Create/Modify

### New Files

| File | Purpose |
|------|---------|
| `harness/semantic_archive.py` | Core semantic archive: embed, store, lookup |

### Modified Files

| File | Change |
|------|--------|
| `agent.py` | Import `find_similar_tapes`, use in `worker_generate_vocabulary()` |
| `pipeline.py` | Call `embed_tape()` after `save_metadata()` in AI post-processing |

### Index Rebuild Script

Located in `harness/semantic_archive.py` as `rebuild_index(output_dir: str)`:
- Iterates all `.json` files in `output_dir`
- Calls `embed_tape()` for each
- Idempotent: re-embedding an existing `tape_id` does `INSERT OR REPLACE`

Run manually:
```bash
python -c "from harness.semantic_archive import rebuild_index; rebuild_index('/path/to/output_dir')"
```

---

## 6. Constraints Checklist

- [x] Works on local NPU (Rock5B) — MXBAI ONNX + onnxruntime NPU provider
- [x] No cloud, no external API — fully offline
- [x] Minimal — SQLite stdlib + numpy, no separate service
- [x] Existing flat markdown memory preserved — unchanged
- [x] RuVector removed/not used — this replaces it
- [x] Does not break existing pipeline

---

## 7. Embedding Dimension

MXBAI models typically output 768-dimensional vectors (mxbai-embed-large-v1). Hard-code this assumption; if the model outputs a different dimension, detect on first load and store in a config table.

```python
DEFAULT_EMBED_DIM = 768
```

---

## 8. Error Handling

- **MXBAI unavailable**: `is_available()` returns `False`, `find_similar_tapes()` returns `[]`, `embed_tape()` is a no-op (logs warning)
- **SQLite errors**: Log and fall back gracefully — tape recording/labeling continues normally
- **Corrupt embedding blob**: `find_similar_tapes()` skips tapes with unreadable embeddings
- **Missing .json sidecar**: Skip during `rebuild_index()`, log warning

---

## 9. Metadata JSON Structure (for reference)

Tape `.json` files contain:
```json
{
  "base_name": "Priya_Wedding_2024-05-15_143022",
  "filename": "Priya_Wedding_2024-05-15_143022.mp4",
  "duration_seconds": 3600,
  "size_bytes": 1500000000,
  "captured_at": "2024-05-15T14:30:22",
  "stop_reason": "manual",
  "validation": { "has_audio": true, "has_video": true, "not_blank": true },
  "transcript": "Full transcript text here...",
  "labels": {
    "title": "Priya's Wedding Highlights",
    "description": "Highlights from Priya and Raj's wedding ceremony and reception.",
    "tags": ["wedding", "indian", "ceremony", "reception"]
  }
}
```

The `embed_tape()` function extracts: `title`, `description`, `transcript`, `tags`, and `corrections` (from grading, if present).
