# Research: ruvector-attn-mincut

**Crate**: `ruvector-attn-mincut` (crates.io / GitHub: `ruvnet/ruvector`)
**Version**: 2.0.4 | **MSRV**: 1.77 | **License**: MIT
**Convoy**: ruvector-crate-research-phase-2

---

## 1. What Mincut Attention Routing Means Technically

Min-cut attention routing replaces the standard all-to-all softmax attention pattern with a graph-theoretic alternative.

**Standard attention**: `Q*K^T → softmax → W*V` — every token attends to every token.

**Min-cut gated attention**: `Q*K^T → graph → min-cut → mask → softmax → W*V`

The process:

1. **Graph construction**: Positive attention logits become weighted directed edges in a graph. Non-positive entries are discarded.
2. **Min-cut partitioning**: Dinic's max-flow / min-cut algorithm partitions the graph (treating token 0 as source `s`, token `seq_len-1` as sink `t`). Edges whose removal cost falls below `lambda * mean_edge_weight` are pruned.
3. **Masked softmax**: Pruned positions are set to `-INF` so softmax naturally zeros them out.
4. **Temporal hysteresis** (`HysteresisTracker`): Gate mask changes only commit after `tau` consecutive agreements — prevents oscillation between steps.
5. **Witness logging**: Every gating decision is SHA-256 hashed for deterministic replay verification.

**Key tunable parameters**:
| Param | Default | Range | Effect |
|-------|---------|-------|--------|
| `lambda` | 0.5 | 0.0–1.0 | Higher = more aggressive pruning |
| `tau` | 2 | 0+ | Higher = more temporal stability |
| `eps` | 0.01 | > 0 | Floor — logits below eps clamped to zero |

**Relation to Routing Transformer**: The conceptual goal is similar to sparse/routing attention (e.g., Routing Transformer, ReZero, Performers). Routing Transformer uses k-means clustering on keys/queries for token bucketing then local+global attention. Min-cut instead uses graph partition. Both aim for sparse attention, but min-cut's graph-theoretic framing is distinctive.

---

## 2. How It Reduces Compute vs Full Attention

The compute reduction comes from **pruning edges before the softmax-V multiplication**:

- Full attention: O(seq_len² · d) — every QK pair contributes to every output
- Min-cut gated: only surviving edges (typically 60–85% of total, at `lambda=0.5`) flow through softmax and the final matmul with V

**Mechanism**:
1. `attn_mincut()` runs Dinic's algorithm on the Q*K^T logits graph
2. Pruned entries are set to `-INF` — softmax turns them to 0
3. The final `matmul_wv()` skips any weight ≈ 0 via an explicit `if wij != 0.0` check

**Claimed savings** (from README "Expected Benefits" table):

| Metric | Improvement |
|--------|-------------|
| KV-cache memory | 15–40% reduction |
| Peak RSS | 10–25% reduction |
| Energy per sample | 10–20% reduction |

**Important caveats**:
- The graph construction + Dinic's algorithm itself adds O(E·√V) per call on the attention graph (E = number of positive logits, V = seq_len). For very short sequences this overhead may exceed the savings.
- Dinic's complexity is `O(V²·E)` worst-case — so for dense attention on long sequences, the overhead of running max-flow could be significant.
- The `dynamic_min_cut()` function adds edges to the solver per positive logit entry, then runs a single s-t cut (s=token 0, t=token seq_len-1). The `tau` parameter (hysteresis) reduces recomputation across steps by stabilizing the mask.

---

## 3. Quality Tradeoffs vs Full Attention

**Claimed**: Coherence delta < 1% degradation (tunable via lambda/tau)

The README references a companion crate `ruvector-coherence` with a `quality_check()` function that computes cosine similarity between baseline (softmax) and gated outputs, and a `passes_threshold` bool.

**How it works in practice**:
- Pruning removes edges with weights below `lambda * mean_weight` — these represent weaker/noisy attention connections
- The hypothesis: many attention edges are near-zero and contribute noise; removing them hurts signal little
- `tau` hysteresis ensures important relationships aren't flickering in/out

**Concerns / verification needed**:
- These claims are from the crate's own documentation, not peer-reviewed benchmarks
- "Coherence" is measured as cosine similarity to the dense softmax output — this is a within-model comparison, not a downstream task accuracy test
- The actual quality degradation on real NLP/VLM tasks (transcription, summarization, etc.) is **not publicly validated**
- The s-t cut uses fixed source=sink (token 0 and last token), which is a specific graph cut strategy — the quality impact depends heavily on whether this choice aligns with the actual attention structure of the model using it

---

## 4. Benchmarks

**Internal tests**: The crate has unit tests (`#[cfg(test)]`) covering:
- `test_dinic_simple_cut` — 4-node graph with 5 edges
- `test_dinic_two_node` — minimal 2-node case
- `test_dynamic_basic` — 3×3 logits matrix
- `test_dynamic_all_negative` — edge case
- `test_dynamic_single_token` — edge case
- `test_softmax_shape_and_finite`, `test_mincut_shape_and_finite`, etc.

**External benchmarks**: **None publicly available.** The README shows a tutorial for running `./scripts/run_mincut_bench.sh --samples 1000 --lambda "0.3 0.5 0.7" --tau "0 2"` but:
- No benchmark results or CSV data are published
- No comparison to established sparse attention methods (Routing Transformer, Linformer, Performer, etc.)
- No peer-reviewed paper citing this crate

**Related academic work**:
- `GraphMinNet` (arXiv:2502.00282) — "Learning Dependencies in Graphs with Light Complexity Minimal Architecture" — related graph-minimization approach
- `RidgeCut` (arXiv:2505.13986) — "Learning Graph Partitioning with Constrained Action Space" — normalized cut for graphs
- PyTorch Geometric's `dense_mincut_pool` — graph pooling using min-cut (NOT attention-related, but same algorithmic family)

---

## 5. Python Bindings

**No Python bindings exist.**

The crate's `Cargo.toml` shows:
```toml
[lib]
crate-type = ["rlib"]   # Rust library only, no cdylib or staticlib
```

Dependencies are pure Rust: `serde`, `serde_json`, `sha2` — no PyO3, no C bindings.

**To use from Python you'd need to**:
1. Write PyO3 bindings (wrap the `attn_mincut()` and `attn_softmax()` functions)
2. Or run it as a separate Rust binary and call via subprocess/gRPC
3. Or use WASM compilation (not designed for this crate)

The related crate ecosystem references `ruvector-coherence` and `ruvector-profiler` — these appear to also be Rust-only. There is no `ruvector-python` or `ruvector-pyo3` crate in the workspace.

---

## 6. Applicability to BeKindRewindAI (Transcriber & Dreamer Agent)

### Potential Benefits

**Transcriber** (Whisper-based or similar):
- Long audio transcripts have repetitive/boilerplate tokens that don't need cross-attention
- If the transcriber model uses transformer layers with full attention, min-cut could reduce KV-cache pressure
- 15–40% KV-cache reduction could enable longer context windows or lower memory footprint

**Dreamer Agent** (world model / imagination unrolls):
- Dreamer-style agents run imagined rollouts — many sequential attention steps over latent states
- Sparse attention could reduce compute per imagination step
- SHA-256 witness chain could help with deterministic replay of imagined sequences

### Significant Barriers

1. **No Python bindings** — BeKindRewindAI is presumably Python-based. Integrating a pure Rust crate requires either PyO3 bindings (nontrivial), a subprocess binary (adds latency), or WASM (not designed for this).

2. **Quality unverified for ASR/transcription** — The < 1% coherence claim is self-reported and measured as cosine similarity to dense attention. For transcription, even small attention quality degradations can cause hallucination or word skipping. Would need empirical validation.

3. **Dinic overhead** — For short sequences (typical ASR: 1500–3000 tokens for audio frames), the O(E·√V) graph cut overhead could erase compute savings. The savings are more compelling for very long contexts (10K+ tokens).

4. **s-t cut design** — Using token 0 as source and last token as sink for every cut is a specific design choice. This may not align well with how attention flows in all model architectures.

5. **No training support** — `ruvector-attn-mincut` is an **inference-time** operator. The gradient flow through the min-cut graph partition is not addressed. If the Dreamer agent needs backprop through attention layers, this can't be dropped into a training loop.

### Verdict

**Short answer**: The ideas in `attn-mincut` are architecturally interesting and the sparse attention approach could theoretically speed up long-context inference, but:

- There are **no published benchmarks** from independent sources
- The quality claims need **empirical validation** on real tasks
- There are **no Python bindings** — integration effort is substantial
- The compute savings depend heavily on sequence length and may not materialize for typical ASR/t transcription batch sizes
- It cannot be used in **training** contexts without gradient support

For BeKindRewindAI's transcriber, you're likely better off with established sparse attention methods (e.g., FlashAttention with sliding window, or Performer/Linear attention) that have PyTorch原生 support and independent validation. For the Dreamer agent's imagination unrolls, if inference speed is the bottleneck and the model uses many attention layers over long sequences, it might be worth an **experimental PyO3 integration** — but treat the performance claims as hypotheses, not facts.

---

## Source Files Reviewed

- `src/lib.rs` — public API re-exports
- `src/mincut.rs` — `DinicSolver`, `dynamic_min_cut()`, `CutResult`, `GatingResult`
- `src/gating.rs` — `attn_softmax()`, `attn_mincut()`, `AttentionOutput`, `compute_logits()`, `row_softmax()`, `matmul_wv()`
- `src/config.rs` — `MinCutConfig` with serde Serialize/Deserialize
- `src/hysteresis.rs` — `HysteresisTracker` (temporal mask stabilization)
- `src/witness.rs` — SHA-256 witness chain
- `README.md` on GitHub (full documentation)
- crates.io page (metadata)
