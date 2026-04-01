# Research: ruvector-cognitive-container — Verifiable Cognitive Pipeline

## What is a Cognitive Container?

A **cognitive container** is a sealed, epoch-based execution environment for running cognitive processing pipelines over graph-structured data. Each epoch produces a **tamper-evident witness receipt** — a cryptographic hash chain linking every epoch to its predecessor, so the entire history can be verified deterministically. Think of it as a blockchain-inspired audit log for cognitive computations: instead of mining, you compute min-cut and spectral metrics.

The container orchestrates five phases per tick:
1. **Ingest** — apply graph deltas (edge add/remove/weight update, node observations)
2. **Min-cut** — Stoer-Wagner-style approximation (minimum weighted vertex degree)
3. **Spectral** — compute Spectral Coherence Score (SCS) = min-cut / total weight, plus Fiedler value and spectral gap
4. **Evidence** — accumulate evidence via SPRT-style mean-of-observations
5. **Witness** — emit a hash-linked `ContainerWitnessReceipt` covering input deltas, min-cut, spectral, and evidence hashes

## Why "Genuinely Insane"

Jordan's "genuinely insane" label is earned by the **combination of ambitions**:

- **Hash-linked witness chain for cognitive processing**: Every epoch's graph state, spectral score, and evidence are hashed into a receipt, then the next receipt hashes the previous one. The entire history is tamper-evident. This is the same pattern as a blockchain merkle tree, applied to VHS tape processing.
- **32.32 fixed-point spectral encoding**: Spectral Coherence Score is stored as a 32.32 fixed-point integer (`f64_to_fixed_32_32`). This is the same representation used in ruQu's quantum coherence calculations.
- **Phase-budgeted tick execution with partial-completion**: If the epoch budget runs out mid-phase, the container continues with a `partial=true` result and a `ComponentMask` tracking which phases completed. Real-time budgets on cognitive work.
- **Deterministic hashing via 4-seed SipHash**: `deterministic_hash()` runs SipHash-2-4 with four different u64 seeds to fill 32 bytes. Not cryptographic (SipHash is not AES), but deterministic across runs on the same platform. Used for everything: edge canonicalization, receipt signing, witness chain.
- **Canonical edge hashing**: Edges are sorted by (u, v), then serialized as three little-endian integers (u64 + u64 + f64), then hashed. This makes the graph representation canonical regardless of insertion order.

## Architecture and Algorithms

### Graph State (`container.rs:80-86`)
- Simple adjacency list: `Vec<(usize, usize, f64)>` edges
- `canonical_hash`: SHA-256-equivalent via SipHash-4-seed over sorted edges
- Min-cut: **minimum weighted vertex degree** approximation (not actual Stoer-Wagner — it's a fast O(E) heuristic, not the O(V log V) deterministic algorithm)

### Spectral State (`container.rs:101-115`)
- `scs` = Spectral Coherence Score = min_cut_value / total_edge_weight
- `fiedler` = just set equal to `scs` (not a real Fiedler value — no actual Laplacian eigendecomposition)
- `gap` = 1.0 - scs

### Evidence State (`container.rs:118-132`)
- Sequential Probability Ratio Test (SPRT) style: accumulates mean(|observations|) over time
- Threshold = 1.0 (hardcoded), not adaptive

### Decision Logic (`container.rs:374-387`)
```
scs >= 0.5 AND evidence < threshold → Pass
scs < 0.2                        → Fail { severity = (1-scs)*10 capped at 255 }
otherwise                         → Inconclusive
```
This is **not** a real Φ calculation. It's a simple threshold decision tree on the SCS ratio.

### Witness Chain (`witness.rs`)
- `ContainerWitnessReceipt`: epoch, prev_hash, input_hash, mincut_hash, spectral_scs (32.32 fixed), evidence_hash, decision, receipt_hash
- `signable_bytes()`: deterministic byte serialization for receipt hashing
- Ring buffer: max 1024 receipts (or `max_receipts` config), oldest evicted when full
- `verify_chain()`: checks self-hash integrity + prev_hash linkage + epoch monotonicity

### Epoch Budget Controller (`epoch.rs`)
- 5 independent phase budgets (ingest/mincut/spectral/evidence/witness) + total budget
- `try_budget(Phase)` checks remaining budget before entering phase
- If total exhausted, no new phases run even if phase-specific budgets remain

### Memory Slab (`memory.rs`)
- Arena bump-allocator within a fixed-size Vec<u8>
- Sub-arenas: graph (1MB), features (1MB), solver (512KB), witness (512KB), evidence (1MB) — default 4MB total
- No actual use of the slab in the current code (the `slab` field is `#[allow(dead_code)]`)

## Relation to Other RuVector Crates

- **ruvector-gnn**: Could feed GNN embeddings as node observations into the Evidence phase. The cognitive container doesn't implement GNN itself — it's the orchestration layer that could consume GNN outputs.
- **ruQu (quantum coherence)**: The 32.32 fixed-point spectral score is the same format ruQu uses. The SCS (min-cut/total) is a rough proxy for ruQu's "quantum coherence via dynamic min-cut" — both measure graph connectivity quality via cut metrics. The container could potentially call ruQu for actual spectral analysis instead of the fake Fiedler approximation.
- **ruvector-consciousness**: The `CoherenceDecision` (Pass/Fail/Inconclusive) is a coarse version of IIT Φ — both attempt to measure "how much the system is integrated vs fragmented." The witness chain is similar to Tononi's Φ* asterisk territory (causal power), but this is a far simpler approximation.

## Key APIs

```rust
// Create
let config = ContainerConfig::default();
let mut container = CognitiveContainer::new(config)?;

// Execute one epoch
let deltas = vec![
    Delta::EdgeAdd { u: 0, v: 1, weight: 1.0 },
    Delta::Observation { node: 0, value: 0.8 },
];
let result = container.tick(&deltas)?;
// result.receipt has epoch, decision, spectral_scs, receipt_hash, etc.

// Verify tamper-evidence
let verification = container.verify_chain();
// VerificationResult::Valid { chain_length, first_epoch, last_epoch }

// Snapshot for persistence/restoration
let snap = container.snapshot();
let json = serde_json::to_string(&snap)?;
```

## Could It Replace or Enhance the Three-Agent Architecture?

**Direct replacement: No.** The container is not an agent system — it's a single-threaded Rust library. Catcher/Grader/Dreamer are distributed AI roles with LLM calls, memory, and external tool use.

**Enhancement: Yes, potentially as a credibility layer:**

1. **Grader → min-cut/spectral evidence**: The Grader grades VHS quality. The cognitive container's min-cut and SCS are a mathematical proxy for "quality/coherence" of the graph. If Grader builds a graph of quality features (audio SNR, video sharpness, artifact presence), SCS could give a fast mathematical quality score.

2. **Dreamer → witness chain**: Dreamer hallucination detection produces "is this real or fabricated?" decisions. The witness chain could record those decisions as an auditable trail — each epoch's Dreamer output is hashed into the receipt. Tampering with a Dreamer verdict would break the chain.

3. **Snapshot/restore for agent continuity**: The container's snapshot/restore means you could save container state after each VHS tape, then restore to continue the chain. This could serve as the "memory" for a future multi-agent orchestration layer.

4. **Catcher → ingest phase**: Catcher catches raw VHS frames. The ingest phase could receive frame-derived graphs (feature edges between detected objects, temporal links between frames). Catcher would become a preprocessor that translates frames into `Delta::EdgeAdd` and `Delta::Observation` events.

**The real insight**: The three-agent architecture and this container are solving different problems. Agents do LLM-level reasoning; the container does verifiable mathematical summarization. They could compose: agents feed the container, container produces verifiable evidence summaries.

## Python Accessibility

**Currently: Not accessible from Python.**

- `crate-type = ["rlib"]` — only produces a Rust static library
- No PyO3, no WASM bindings, no mcporter/mcp-gate exposure
- No Python SDK in the Rust codebase

**To make it accessible**, one would need:
1. **PyO3 bindings**: Wrap `CognitiveContainer::new`, `tick`, `verify_chain` as a Python class — requires adding `pyo3` to Cargo.toml and writing a `lib.rs` PyO3 entrypoint
2. **WASM**: Recompile as `crate-type = ["cdylib", "rlib"]` with `wasm-bindgen` — then use in Python via wasmtime or browser
3. **mcporter/mcp-gate**: Expose via `@ruvector/mcp-server` or similar MCP server — but no MCP tool definitions found in this crate

**Current best path**: Run as a standalone Rust binary/service, call via HTTP/JSON from Python. The `ContainerSnapshot` serializes to JSON, so `container.tick()` → HTTP POST → Python could work today without any new bindings.

## Summary

ruvector-cognitive-container is a **verifiable cognitive pipeline orchestrator** with a blockchain-inspired witness chain. Its core claim: run cognitive computations (ingest, graph analysis, evidence accumulation) inside a sealed container that produces tamper-evident receipts for every epoch. The "insane" part is applying cryptographic hash chaining and merkle-style verification to what is essentially a VHS quality scoring system.

The algorithms are **simplified approximations** (min-cut via minimum weighted degree, Fiedler value = SCS, SPRT evidence = running mean) — not the real algorithms. But the architecture is sound: deterministic, budgeted, verifiable, and potentially composable with real GNN and quantum coherence libraries when they're available.

**BeKindRewindAI relevance**: Low as a direct replacement, but high as a **credibility/integrity layer** if the three-agent system grows to need auditable quality decisions. The witness chain pattern is worth adopting for any grading/dreaming output that needs to be verifiable later.
