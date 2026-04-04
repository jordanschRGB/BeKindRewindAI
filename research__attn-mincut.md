# Research: attn-mincut — Mincut Attention Routing

## 1. What Mincut Attention Routing Means Technically

**Standard softmax attention** applies `softmax(Q * K^T)` uniformly over all token pairs — every token attends to every other token (dense, O(n²)).

**Mincut attention routing** replaces this with a graph-theoretic approach:

1. **Graph construction**: Positive Q*K^T logits become weighted directed edges in a graph. Non-positive entries are discarded immediately.

2. **Min-cut partitioning**: Dinic's max-flow/min-cut algorithm partitions the graph. Edges whose removal cost falls below `lambda * mean_weight` are pruned (gated off).

3. **Masked softmax**: Pruned positions are set to `-INF` so softmax zeros them out. Surviving edges are row-normalized and multiplied by V.

4. **Temporal hysteresis** (`HysteresisTracker`): Gate masks don't flip immediately on new evidence — a flip only commits after `tau` consecutive agreements. This prevents oscillation.

5. **Witness logging**: Every gating decision is hashed with SHA-256 for deterministic replay on a second machine.

**Key tunable parameters**:
- `lambda` (0.0–1.0): Sparsity budget. Higher = more pruning.
- `tau` (0+): Hysteresis steps before gate flip commits.
- `eps` ( > 0): Safety floor — logits below eps are clamped to zero before graph construction.

## 2. How It Reduces Compute vs Full Attention

| Metric | Reduction |
|--------|-----------|
| KV-cache memory | **15–40%** |
| Peak RSS | **10–25%** |
| Energy per sample | **10–20%** |

The mechanism: pruned attention edges skip both the softmax computation and the V-multiplication step. Since KV-cache is a major memory bottleneck in long sequences, sparsity directly reduces allocation. Fewer active attention paths also means less data movement and compute.

## 3. Quality Tradeoffs vs Full Attention

**Coherence degradation: < 1%** (tunable via lambda/tau)

The tradeoffs are controlled by configuration:
- Lower `lambda` → denser attention → higher quality but more compute
- Higher `tau` → more temporal stability → smoother outputs but slower adaptation to new patterns

The hysteresis mechanism is key: it prevents the mask from thrashing between steps, which is where quality loss typically manifests in sparse attention schemes.

## 4. Benchmarks

From the crate README:

| Metric | Typical improvement |
|--------|-------------------|
| KV-cache memory | 15–40% reduction |
| Peak RSS | 10–25% reduction |
| Energy per sample | 10–20% lower |
| Coherence delta | < 1% degradation |

The crate ships a `ruvector-coherence` integration for measuring output quality after gating, and `ruvector-profiler` for memory/latency benchmarking.

**Note**: Independent benchmarks from third parties have not been widely published yet. These numbers are vendor-reported.

## 5. Python Bindings

**No direct PyO3 Python bindings** are published on PyPI.

Access paths:
1. **`ruvector-attention-wasm`** (npm: `@ruvector/attention-wasm`) — WASM-compiled attention mechanisms including the mincut approach, callable from JavaScript/TypeScript. Python could use this via Pyodide or a JS subprocess bridge.
2. **`ruvector-attention-node`** — Node.js bindings for the broader attention crate.
3. **Direct Rust integration** — Compile via PyO3 or use `cargo build` + FFI.
4. **`ruvector-mcporter`** — The mcporter API may expose the mincut operator as a service, but this is not confirmed as a Python-native path.

**The mincut operator is NOT yet available as a standalone pip-installable Python package.**

## 6. Applicability to BeKindRewindAI (Transcriber + Dreamer Agent)

### Transcriber (Whisper-style)

**Potentially beneficial** for long audio transcripts where:
- KV-cache pressure is high due to long sequence lengths
- Some attended tokens are semantically irrelevant (background noise, filler words)

The 15–40% KV-cache reduction could enable longer context windows without OOM. However:
- The < 1% coherence degradation may affect transcription precision for rare words or timestamps
- The current transcriber likely uses HuggingFace Transformers, not a custom Rust attention layer — integration would require replacing the attention mechanism

### Dreamer Agent (memory loop + latent planning)

**Moderate relevance**:
- Structure-aware attention could help the Dreamer focus on semantically coherent memory retrieval patterns
- The hysteresis mechanism is well-suited for temporal memory loops where stability matters
- Vocabulary generation (Worker's Whisper vocabulary lists) is not compute-bound on attention — likely not impacted

### Verdict

| Component | Relevance | Confidence |
|-----------|-----------|------------|
| Transcriber (long audio) | Medium-High | KV-cache reduction would help, but integration cost is high |
| Dreamer Agent | Medium | Temporal stability + sparsity fits memory loops |
| Worker (vocab generation) | Low | Not attention-bound |

**Integration cost is significant**: BeKindRewindAI would need to swap out its current attention mechanism (likely HF Transformers). The `ruvector-mincut-gated-transformer` crate (v0.1.0) is a full transformer with integrated mincut gating — this could theoretically replace a layer, but no plug-in compatibility with existing Python ML frameworks is documented.

**Bottom line**: attn-mincut is a legitimate sparse attention technique with solid theoretical backing (graph cut = mincut) and measurable efficiency gains. It is NOT a drop-in replacement for any current Python ML component, but could be used to build a more efficient custom model if the team is willing to go Rust-first for the attention-critical path.

---

## Related Crates

| Crate | Role |
|-------|------|
| `ruvector-attn-mincut` | Core mincut attention operator |
| `ruvector-mincut` | General dynamic mincut solver |
| `ruvector-mincut-gated-transformer` | Full transformer with mincut gating |
| `ruvector-attention-wasm` | WASM attention (includes mincut path) |
| `ruvector-coherence` | Quality measurement after gating |
| `ruvector-profiler` | Memory/power/latency benchmarking |

---

**Sources**: crates.io (ruvector-attn-mincut 2.0.4), github.com/ruvnet/RuVector/crates/ruvector-attn-mincut README, docs.rs/ruvector-attn-mincut