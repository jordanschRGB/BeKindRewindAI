# Research: attn-mincut — Mincut Attention Routing

**Crate**: `attn-mincut` (ruvector-attn-mincut v2.0.4)  
**Researched by**: Lark (polecat)  
**Bead**: 77cfc90b-0c2e-42b3-b2b1-1a47619f5d3c  
**Convoy**: RuVector Crate Research — Phase 2 (20ef8f34)

---

## 1. What Mincut Attention Routing Means Technically

### Algorithm Overview

The crate replaces standard softmax attention with a **graph-theoretic approach** using Dinic's max-flow/min-cut algorithm:

1. **Graph Construction**: Q·K^T logits are converted to a weighted directed graph where positive logits become weighted edges
2. **Min-cut Partitioning**: Dinic's algorithm computes an s-t min-cut to partition the graph, pruning low-value attention edges
3. **Gated Softmax**: Surviving edges are masked with −∞, row-softmax normalizes them, then multiplied by V

### The Graphcut/Mincut Formulation

| Element | Role |
|---------|------|
| Source (s) | token 0 |
| Sink (t) | token seq_len − 1 |
| Edges | positive attention logits (weights = logit values) |
| Min-cut | minimum total weight edge cut separating source from sink |

Edges below `threshold = lambda * mean_edge_weight` are pruned. This is a **normalized cut** variant, not a ratio cut.

### Key Modules

| Module | Purpose |
|--------|---------|
| `graph` | Builds `AttentionGraph` from logits (only positive entries become edges) |
| `mincut` | `DinicSolver` + `dynamic_min_cut` for s-t partitioning |
| `gating` | `attn_mincut()` and `attn_softmax()` operators |
| `hysteresis` | `HysteresisTracker` prevents mask oscillation between timesteps |
| `witness` | SHA-256 hashing for deterministic verification |

---

## 2. How It Reduces Compute vs Full Attention

### Computational Complexity

| Attention Type | Complexity |
|----------------|------------|
| Standard attention | O(seq_len² · d) |
| attn-mincut overhead | O(V² · E) worst case for Dinic; O(E·√V) for unit capacity |

V = seq_len, E = number of positive logits (sparse case: ≪ seq_len²).

The mincut computation is relatively cheap vs the attention matmul. Savings come from **sparse KV-cache usage** after pruning edges.

### Reported Benefits

| Metric | Improvement |
|--------|-------------|
| KV-cache memory | 15–40% reduction |
| Peak RSS | 10–25% reduction |
| Energy per sample | 10–20% reduction |

### Sparsity Control Knobs

- `lambda` (0.0–1.0): Higher = more aggressive pruning
- `eps`: Filters near-zero logits before graph construction
- `tau`: Temporal hysteresis steps to stabilize masks over time

---

## 3. Quality Tradeoffs vs Full Attention

- **No formal approximation guarantee** stated in the documentation
- The min-cut itself is computed exactly via Dinic's algorithm
- README claims **< 1% coherence degradation** (tunable via lambda/tau)
- Paired with `ruvector-coherence` for quality measurement
- `attn_mincut()` returns `AttentionOutput { output, gating }` where `gating.edges_kept / edges_total` reports sparsity level
- For very small sequences (< 2 tokens), returns empty mask
- All-negative logits result in zero edges kept
- NaN handling for fully-gated rows (replaced with 0)

---

## 4. Benchmarks

### Available Numbers (from crate README)

| Metric | Value |
|--------|-------|
| KV-cache reduction | 15–40% |
| Peak RSS reduction | 10–25% |
| Energy/sample reduction | 10–20% |
| Coherence delta | < 1% |

### Benchmark Infrastructure

- `ruvector-profiler` for memory, power, latency benchmarking
- `ruvector-coherence` for quality measurement
- `./scripts/run_mincut_bench.sh --samples 1000 --lambda "0.3 0.5 0.7" --tau "0 2"`

### Gaps in Benchmark Data

- **No absolute latency numbers** (e.g., ms per token)
- **No comparison to FlashAttention or other sparse attention methods**
- **No model quality benchmarks** (perplexity, accuracy on tasks)
- The "10–20% energy reduction" appears vendor/marketing-driven

---

## 5. Python Bindings

**Direct Python API: NO**

- `crate-type = ["rlib"]` (Rust library only)
- No PyO3, pyo3-bindgen, or cpython bindings
- No Python wheel on PyPI

### RuVector Python Ecosystem

- `@ruvector/ruvllm` — npm package for LLM inference (uses CLI subprocess wrapper, not native bindings)
- No documented Python bindings for attn-mincut specifically

### Integration Path for Python

To use attn-mincut from Python, you would need:
1. Add PyO3 bindings and build as a native extension
2. OR wrap via FFI/Language Server Protocol (add `wasm` target)
3. OR run as a sidecar HTTP service (like ruvector-server pattern)

---

## 6. Applicability to Transcriber / Dreamer in BeKindRewindAI

### Transcriber (Whisper)

**Fit: LOW**. attn-mincut targets transformer self-attention, not audio feature extraction. Whisper-based transcription does not use transformer attention in the way this crate accelerates. Not a good fit.

### Dreamer Agent (Memory Loop)

**Fit: MEDIUM**. The Dreamer agent works with sequential decision-making and memory replay. If it uses transformer-based attention over long context windows, mincut attention could:

- Reduce KV-cache pressure for long memory traces (15–40% claimed)
- Lower memory footprint during replay
- Hysteresis tracker helps stabilize gating over time

**However**:
- BeKindRewindAI's Dreamer appears to use **llama-cpp-python** — not a Rust transformer
- Even if Dreamer used a Rust transformer, benefit depends on **attention sparsity patterns in your specific data**
- No published benchmarks on actual video/voice AI tasks

### Bottom Line

**attn-mincut is a low-level Rust primitive** for transformer attention optimization. Not a drop-in speedup for Python-based transcription or LLM agents. Benefits are theoretical (15–40% KV-cache reduction) but unverified on real workloads.

If BeKindRewindAI's Dreamer used a Rust-based transformer with long context windows, you would need to:
1. Benchmark your specific attention patterns
2. Add Python bindings or build a sidecar service
3. Validate quality degradation is acceptable
