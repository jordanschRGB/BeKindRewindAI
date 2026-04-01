# Research: prime-radiant — Coherence/Hallucination Detection Engine

## What It Does Technically

**prime-radiant** is a Rust crate that implements a *coherence gate* — mathematical infrastructure that detects structural inconsistencies (contradictions) in AI system beliefs before allowing actions.

### Core Concepts

1. **Sheaf Graph**: State is modeled as a typed graph where:
   - **Nodes** = facts, beliefs, memories, claims (each carrying a fixed-dimensional state vector)
   - **Edges** = constraints between nodes (citations, entailment, causality)
   - **Restriction maps (ρ)** = linear transformations encoding how one node constrains another

2. **Coherence Energy Formula**:
   ```
   E(S) = Σ wₑ · ‖ρᵤ(xᵤ) - ρᵥ(xᵥ)‖²
   ```
   - Lower energy = more coherent (things agree)
   - Higher energy = contradiction detected
   - Example: "Meeting at 3pm" [0.9, 0.1] vs "Meeting at 4pm" [0.1, 0.9] → Energy = 1.28 (high incoherence)

3. **Compute Ladder**: Energy thresholds route decisions to appropriate lanes:
   | Energy | Lane | Latency | Action |
   |--------|------|---------|--------|
   | < 0.1 | Reflex | < 1ms | Immediate approval |
   | 0.1-0.4 | Retrieval | ~10ms | Fetch more evidence |
   | 0.4-0.7 | Heavy | ~100ms | Deep analysis |
   | > 0.7 | Human | async | Escalate to human |

4. **Governance Layer**: Every decision produces:
   - **Witness Records** — Blake3 hash-chained cryptographic proofs
   - **Policy Bundles** — Versioned, signed threshold configurations
   - **Lineage Records** — Full provenance for graph modifications

### Dependencies
The crate integrates with: `ruvector-core`, `ruvector-gnn`, `ruvector-attention`, `ruvector-nervous-system`, `ruvector-sona`, `ruvllm`, `cognitum-gate-kernel`, and optional SIMD/GPU acceleration.

---

## Python Access

**No native Python bindings.** The crate is Rust-only (v0.1.0, published 2026-01-23).

### Options for Python Integration

| Approach | Feasibility | Overhead |
|----------|------------|----------|
| **CLI subprocess** | Easy | High latency (process spawn per check) |
| **PyO3 bindings** | Needs wrapping | Low latency, but must be built |
| **HTTP sidecar (ruvector-server)** | Moderate | Network latency |
| **Embed in ruvllm npm package** | Already done for ruvllm | ruvllm has Python access via npm |
| **WASM/WebAssembly** | Supported via wgpu | Browser-only, not server Python |

The `ruvllm` feature provides LLM integration, but ruvllm itself is accessed via `@ruvector/ruvllm` npm package (Node.js), not Python.

**Verdict**: For Python/BeKindRewindAI, the most practical path is either:
1. Build a CLI wrapper around a compiled `prime-radiant` binary
2. Use the HTTP REST API if a server variant is exposed
3. Write PyO3 bindings (non-trivial engineering effort)

---

## Does It Provably Beat Vanilla LLM Hallucination Detection?

### Claims Made by the Project
- "Mathematical, not heuristic" coherence detection
- "Proves structural consistency" vs "guesses about probability"
- Provides "cryptographic proof" via witness records

### Honest Assessment

**Theoretical Strengths**:
- Sheaf Laplacian coherence is mathematically rigorous for measuring constraint violations
- Deterministic witness chain provides auditability that probabilistic confidence scores lack
- Energy-based gating is interpretable vs black-box confidence

**Gaps and Skepticism**:

1. **No independent benchmarks**: I found no third-party benchmarks comparing prime-radiant hallucination detection against baselines like:
   - Self-consistency checking (Wang et al.)
   - TruthfulAI / Constitutional AI
   - Uncertainty quantification via perplexity
   - RAG verification with external knowledge

2. **Requires embeddings**: The system works on vector embeddings of claims. You still need:
   - An embedding model to encode facts/claims
   - A mechanism to build the graph edges (what connects to what?)
   - The restriction maps (ρ) — identity is simple, but learned maps require training

3. **No free lunch**: The coherence gate detects *inconsistency* between claims, but:
   - It cannot detect claims that are simply *wrong but internally consistent*
   - Two coherent false beliefs will pass through
   - Quality depends entirely on the embedding space quality

4. **Version 0.1.0, early stage**: Only 96 downloads in 90 days. "docs.rs failed to build" — incomplete documentation. Not production-proven.

5. **Theoretical vs empirical**: The mathematical formalism is sound, but "provably beats" requires empirical validation on held-out hallucination datasets (e.g., TruthfulQA, HaluEval). No such validation has been published.

**Verdict**: The *approach* is theoretically interesting and well-motivated. But "provably beats vanilla LLM" is **unproven marketing** at this stage. It could be better in specific narrow cases, but no evidence.

---

## Benchmarks

From the README, claimed performance (CPU baseline):

| Operation | Latency | Throughput |
|----------|---------|------------|
| Single residual | < 1μs | 1M+ ops/sec |
| Graph energy (10K nodes) | < 10ms | 100 graphs/sec |
| Incremental update | < 100μs | 10K updates/sec |
| Gate evaluation | < 500μs | 2K decisions/sec |

SIMD (AVX-512) claims 8-16x speedup; GPU (wgpu) also mentioned.

**No third-party benchmarks.** These are self-reported. No comparison to:
- Vanilla LLM hallucination detection baselines
- Other coherence/checking approaches
- Established benchmarks (TruthfulQA, HaluEval, FActScore)

---

## Replacing/Enhancing Dreamer Agent in BeKindRewindAI

### Current Dreamer Role in BeKindRewindAI
Based on the research context, the Dreamer agent likely handles:
- Memory replay / consistency checking across conversation history
- Detecting when the system contradicts itself
- Vocabulary consistency verification

### How prime-radiant Could Help

**As a replacement for Dreamer's hallucination detection**:
- Would provide mathematical coherence scoring instead of probabilistic confidence
- Better audit trail via witness records
- Compute ladder for graduated response (refuse vs escalate)

**Architecture integration**:
```
User Transcription → Embed claims (OpenAI/Cohere/etc.)
                    → Build SheafGraph (claim nodes + retrieved memory edges)
                    → Compute coherence energy
                    → Gate decision (Reflex/Retrieval/Heavy/Human)
                    → Produce witness record
```

**Enhancements over current Dreamer**:
- Deterministic rejection with cryptographic proof
- Formal audit trail for compliance
- Multi-level escalation path

### Practical Challenges for BeKindRewindAI

1. **Python integration**: Dreamer is Python-based. prime-radiant has no Python bindings.

2. **Embedding dependency**: Need to embed all facts/claims — requires an embedding model. If BeKindRewindAI already uses embeddings for vocabulary search, this could reuse that infrastructure.

3. **Graph construction**: Who decides which edges exist? prime-radiant needs a graph of constraints. For BeKindRewindAI:
   - Edges = temporal proximity, shared vocabulary, semantic similarity above threshold
   - These would need to be constructed from the existing memory/vocabulary data

4. **Threshold tuning**: The compute ladder thresholds (0.1, 0.4, 0.7) are arbitrary without empirical tuning on BeKindRewindAI's specific vocabulary/task domain.

5. **Added complexity**: The existing BeKindRewindAI 3-agent pipeline (Orchestrator/Agent/Dreamer) adds another system. Is the marginal improvement worth the added Rust dependency and embedding pipeline changes?

---

## Summary

| Question | Answer |
|----------|--------|
| **What it does** | Sheaf Laplacian coherence engine — detects contradictions as energy in a constraint graph |
| **Python access** | None. CLI wrapper or PyO3 bindings needed |
| **Provably better than vanilla LLM?** | Theoretically sound but **unproven**. No independent benchmarks. Marketing claim without evidence. |
| **Benchmarks** | Self-reported only. No third-party validation. |
| **Replace Dreamer?** | Could enhance with mathematical coherence scoring + audit trail, but requires significant integration work and has no Python bindings. |

### Bottom Line

prime-radiant is an *interesting theoretical approach* to AI safety via structural coherence verification. The mathematics are legitimate (sheaf Laplacians for constraint satisfaction). However:

1. It's v0.1.0 with 96 downloads — extremely early
2. No published benchmarks or third-party validation
3. No Python bindings — major barrier for BeKindRewindAI
4. Requires building an entire embedding + graph construction pipeline around it
5. "Provably beats" is marketing without evidence

**Recommendation**: Do NOT replace Dreamer with prime-radiant currently. The integration cost is high and the empirical benefits are unproven. If BeKindRewindAI wants better hallucination detection:
- Better approach: Ensemble of perplexity checking + self-consistency + RAG verification
- If pursuing prime-radiant: Wait for v1.0, Python bindings, and published benchmarks

---

## References

- Crates.io: https://crates.io/crates/prime-radiant
- GitHub: https://github.com/ruvnet/RuVector/tree/main/crates/prime-radiant
- Architecture gist: https://gist.github.com/ruvnet/e511e4d7015996d11ab1a1ac6d5876c0
- RuVector README: https://github.com/ruvnet/RuVector
