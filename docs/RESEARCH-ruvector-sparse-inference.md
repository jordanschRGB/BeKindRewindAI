# Research: ruvector-sparse-inference

## 1. What sparse vector operations it provides

**ruvector-sparse-inference v2.0.6** is a **PowerInfer-style sparse inference engine** — not a standalone sparse vector library. It accelerates neural network forward passes by exploiting the power-law distribution of activations where ~10% of neurons handle ~90% of computations.

### Core sparse operations

| Operation | Description |
|-----------|-------------|
| `SparseFfn` | Two-layer FFN (W1 → activation → W2) computed only for active neurons. W2 stored transposed so neuron-indexed column access is contiguous row access. |
| `forward_sparse(input, active_neurons)` | Computes FFN for only the predicted-active subset of neurons, skipping cold weights entirely. |
| `SparseEmbeddingProvider` | Integrates with RuVector. `embed(tokens)`, `embed_batch()`, `calibrate()`. GGUF model loading (`from_gguf`, `from_gguf_bytes`). |
| `LowRankPredictor` | O(r·d) P·Q matrix factorization predicts which neurons will activate before the sparse FFN runs. |
| `SwiGLUFfn` | Sparse variant of SwiGLU activation (SiLU + gating), used in modern LLMs. |

### Precision lanes (3/5/7-bit quantization)

The crate has a unique **π-based quantization system** for low-precision inference:
- **Bit3** (−4..3): reflex signals, gating, anomaly triggers
- **Bit5** (−16..15): streaming embeddings, drift detection  
- **Bit7** (−64..63): reasoning, synthesis, micro-LoRA
- **Float32**: full precision / training

Signals "graduate" up lanes on novelty/drift, down on stability. π constants avoid power-of-2 resonance in low-bit math.

### SIMD support

AVX2/FMA (256-bit), SSE4.1 (128-bit), NEON (ARM), WASM SIMD. SIMD-accelerated GELU/SiLU via polynomial approximations.

### Model architectures supported

LlamaModel, LlamaLayer, LlamaAttention, LlamaMLP, BertModel, BertLayer, BertEmbeddings, LFM2Model, LFM2Layer, GroupedQueryAttention, MultiHeadAttention, GatedConv1d. GGUF file parsing (Q4_0 through Q6_K).

---

## 2. How sparse representations help vs dense (SBERT-style) embeddings

These are **two different concepts** that address different bottlenecks:

### SBERT/dense embeddings
- A dense embedder (BERT, BGE, Qwen3-Embedding) maps text → a **fixed-dimension dense vector** (e.g., 768 or 1024 floats) where *every dimension is non-zero*.
- Retrieval: you compute cosine similarity between dense vectors.
- Storage cost is fixed and predictable (dimension × corpus size × 4 bytes).

### This crate's "sparse" is about **model inference sparsity**, not retrieval representation sparsity

`ruvector-sparse-inference` doesn't produce sparse *embeddings* for storage. It produces sparse *neural network activations* to **speed up the embedding generation step itself**. The output embedding is still a dense vector.

### However, there IS a connection to vocabulary/sparse search

The `SparseEmbeddingProvider` uses a **LowRankPredictor** to predict which FFN neurons will fire for a given input. This is similar in spirit to learned sparse retrieval (SPLADE, LACONIC) which predict which vocabulary terms are relevant. The crate also has a `sparsity_threshold` knob that controls how many neurons are "hot" vs "cold".

### Key distinction for BeKindRewindAI
- If you want **faster embedding generation**: this crate helps (2–10× speedup with <1% accuracy loss per the README).
- If you want **sparse retrieval representations** (BM25-style lexical + semantic hybrid): this is not the right crate — look at SPLADE, LACONIC, or ruvector-postgres with its 230+ SQL functions for hybrid search.

---

## 3. Benchmarks vs dense approaches

From the README (v0.1.31, v2.0.6):

| Sparsity Level | Latency | Speedup vs Dense | Memory Reduction |
|----------------|---------|------------------|------------------|
| 10% active neurons | 130µs | **52× faster** | 83% reduction |
| 30% active | 383µs | **18× faster** | 83% reduction |
| 50% active | 651µs | **10× faster** | 83% reduction |
| 70% active | 912µs | **7× faster** | 83% reduction |

Target performance:
- LFM2 350M: ~5–10ms/sentence, **2.5× speedup**, 40% memory reduction
- Sentence-transformers: ~2–5ms/sentence, **2× speedup**, 30% memory reduction
- Llama 7B: 50–100ms/token, **5–10× speedup**, 50% memory reduction

v0.1.31 improvements: W2 transpose storage optimization + SIMD GELU/SiLU = **6× speedup** over prior version.

### Sparse vs dense retrieval benchmarks (separate from this crate)

From production research (BigData Boutique, March 2026):

| Model | Type | nDCG@10 (BEIR avg) | GPU Required |
|-------|------|-------------------|--------------|
| BM25 | Classic sparse | 42.9 | No |
| SPLADE v3 | Learned sparse | 51.3 | For encoding only |
| LACONIC-8B | Learned sparse | **60.2** | For encoding only |
| Dense models | Dense | 63–70 | Yes (query-time) |

LACONIC achieves **top-15 on MTEB** while using **71% less index memory** than equivalent dense models.

---

## 4. Python bindings

**No published PyPI package.** No PyO3 bindings visible in the crate. The only Python-adjacent path is:

1. **WASM**: The crate has a `backend::wasm::WasmBackend` and a `#[wasm_bindgen]` API (`create_sparse_engine`, `infer`). This can be called from JavaScript/TypeScript. There is no published WASM npm package for this crate specifically.

2. **mcporter**: The RuVector ecosystem uses `mcporter` as its server-side API layer. The `SparseEmbeddingProvider` implements the `EmbeddingProvider` trait for RuVector's internal integration. It is not exposed as a standalone mcporter endpoint.

3. **Direct Rust**: You can call this from Rust code directly via `Cargo.toml` dependency:
   ```toml
   ruvector-sparse-inference = "2.0.6"
   ```
   Then use `SparseEmbeddingProvider::from_gguf(path)?` and call `.embed(tokens)`.

4. **GGUF models**: The crate loads GGUF quantized models. Libraries like `llama-cpp-python` or `sentence-transformers` (with.gguf support) can run equivalent models without this crate.

---

## 5. Would sparse vectors help vocabulary/search in BeKindRewindAI?

**Indirectly — but not via this crate directly.**

### How BeKindRewindAI's vocabulary works today
The Archivist/Worker/Dreamer agents use:
- Vocabulary lists built from Whisper transcripts
- Flat file storage for vocabulary entries
- LLM-generated titles, descriptions, tags for each transcript segment

### What BeKindRewindAI actually needs

| Need | Right tool |
|------|-----------|
| Faster embedding of transcript chunks | `ruvector-sparse-inference` (via Rust integration) — but the current encode step is not the bottleneck |
| Hybrid lexical + semantic search (vocabulary terms, VHS tape metadata) | ruvector-postgres (BM25 + vector columns, 230+ SQL functions) |
| Learned sparse embeddings (SPLADE-style term expansion) | ruvector-sparse-inference's `SparseEmbeddingProvider` could generate these if integrated into the pipeline |
| Reducing memory for vocabulary storage | LACONIC-style sparse retrieval or ruvector-postgres with sparse BM25 columns |

### Recommendation

The **vocabulary/search problem** in BeKindRewindAI is best solved by **ruvector-postgres** (PostgreSQL extension with pgvector-compatible API + BM25 hybrid search). The `ruvector-sparse-inference` crate would only help if:

1. You are encoding a very large corpus of VHS transcripts and the encoding step is genuinely the bottleneck (not likely — encoding is a one-time cost per transcript)
2. You want to run the model on **edge hardware** (e.g., a NAS or old MacBook) where sparse inference saves significant memory/CPU
3. You integrate `SparseEmbeddingProvider` into the Archivist pipeline to generate **sparse lexical + dense semantic hybrid embeddings** stored in ruvector-postgres

For a flat-file vocabulary system, sparse vectors add complexity without clear benefit unless the vocabulary grows to 100k+ terms requiring ANN search.

### Bottom line

`ruvector-sparse-inference` = **model inference speedup** crate (PowerInfer-style). For vocabulary/search in BeKindRewindAI, the relevant crate is **`ruvector-postgres`** for hybrid BM25 + vector storage, and **SPLADE/LACONIC-style sparse embeddings** if you want learned lexical expansion. This crate could *generate* sparse embeddings if integrated as a Rust dependency, but it is not a drop-in solution for the current flat-file vocabulary backend.

---

## Source data

- Crates.io: https://crates.io/crates/ruvector-sparse-inference
- Docs.rs: https://docs.rs/ruvector-sparse-inference/2.0.6
- GitHub: https://github.com/ruvnet/ruvector/tree/main/crates/ruvector-sparse-inference
- Sparse vs dense retrieval: https://bigdataboutique.com/blog/sparse-vs-dense-vectors-how-lexical-and-semantic-search-actually-work (March 2026)
