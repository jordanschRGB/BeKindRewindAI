# Research: prime-radiant (Coherence/Hallucination Engine)

**Bead**: de88ee14-3e2a-465d-9bdd-555aac20f295
**Crate**: `/workspace/rigs/63341274-b0d1-4a38-aee7-57b47162d52e/ruvector-browse/crates/prime-radiant/`
**Researcher**: Slate-polecat-63341274@28eb9c76

---

## 1. What Does This Crate Do Mathematically?

**Prime-radiant is a universal coherence engine based on sheaf Laplacian theory.** It provides structural consistency guarantees by modeling knowledge as a sheaf graph where:

- **Nodes** = facts, beliefs, entities (carrying fixed-dimensional state vectors called "stalks")
- **Edges** = constraints between entities via **restriction maps** (linear transforms `ρ: F(u) → F(v)`)
- **Residual** = `r_e = ρ_source(x_source) - ρ_target(x_target)` — measures local inconsistency at each edge
- **Coherence energy** = `E(S) = Σ(w_e * ||r_e||²)` — global incoherence measure

The key insight from algebraic topology: if all local residuals are zero (or small), the global section is **globally consistent**. This is a mathematical proof, not a heuristic.

**Domain table** (from lib.rs):

| Domain | Nodes | Edges | Residual = |
|--------|-------|-------|------------|
| AI Agents | Facts, hypotheses | Citations, implication | Contradiction energy |
| Finance | Trades, positions | Market dependencies | Regime mismatch |
| Medical | Vitals, diagnoses | Physiological causality | Clinical disagreement |
| Robotics | Sensors, goals | Physics, kinematics | Motion impossibility |
| Security | Identities, permissions | Policy rules | Authorization violation |

---

## 2. How Does It Compute "Coherence Energy"?

**Core algorithm** (`src/coherence/energy.rs`):

```rust
// For each edge:
r_e = rho_source(x_source) - rho_target(x_target)  // vector difference
||r_e||² = sum(r_e[i]² for i in dims)             // squared L2 norm  
energy_contribution = w_e * ||r_e||²               // weighted by edge weight

// Total:
E(S) = sum(energy_contribution for all edges)
```

**Restriction maps** (`engine.rs`):
- **Identity**: `y = x` (no transformation — states must directly match)
- **Projection**: selects specific dimensions `y = x[selected_dims]`
- **Learned** (feature `learned-rho`): GNN-learned transforms via `ruvector-gnn`

**Performance targets** (from `lib.rs`):
- Single residual: < 1μs
- Full graph energy (10K nodes): < 10ms
- Incremental update (1 node): < 100μs

**Optional accelerators**:
- SIMD (`wide::f32x8` for AVX2/AVX-512)
- GPU (`wgpu` compute shaders)
- Parallel (`rayon` for edges ≥ 100)

---

## 3. How Does the Compute Ladder Work?

**4-lane escalation system** (`src/execution/ladder.rs`):

| Lane | Latency | Trigger |
|------|---------|---------|
| **Reflex** (0) | <1ms | Default — energy < reflex threshold |
| **Retrieval** (1) | ~10ms | Transient energy spike |
| **Heavy** (2) | ~100ms | Sustained incoherence (persistence window exceeded) |
| **Human** (3) | async | Energy exceeds all automatic thresholds |

**Default thresholds** (`LaneThresholds::default()`):
- `reflex`: 0.2
- `retrieval`: 0.5  
- `heavy`: 0.8

**Persistence detection**: Tracks energy history per scope. If energy stays above reflex threshold for the persistence window (default 5s), escalates to Heavy lane.

**Fast path** (`gate.rs:evaluate`):
```
if energy < reflex_threshold AND action.is_low_risk():
    return GateDecision::allow(Reflex)  // No witness needed
```

**Full path**: Computes lane from energy, adjusts for action impact, checks persistence, creates mandatory `WitnessRecord` with hash chain.

---

## 4. How Would It Replace Dreamer's LLM-Based Hallucination Detection?

**Current Dreamer approach** (from architecture): Use an LLM to evaluate whether output contradicts known facts.

**prime-radiant approach**: Mathematical proof via sheaf coherence.

```
Traditional (LLM-based):
  "Did the model hallucinate?" → LLM judges → probabilistic guess

prime-radiant (sheaf-based):
  Context node [fact₁, fact₂, ...] → Edge → Response node
  Compute: r = context_embedding - response_embedding
  If ||r||² < threshold → PROVABLY coherent (no LLM needed)
```

**LLM Validation module** (`src/ruvllm_integration/coherence_validator.rs`):
- Builds sheaf graph: context node, response node, optional support nodes
- Edges enforce semantic consistency between context and response
- Energy quantifies hallucination: high energy = response contradicts context
- Returns `ValidationResult { allowed, energy, witness }`

**"Mathematical proof" claim**: The system doesn't prove facts are TRUE, it proves the response is **coherent with** the knowledge graph. If the graph is wrong, the coherence is wrong — but within the graph's scope, coherence is deterministic.

**Key difference**: LLM judges are **intrinsic** (model evaluating itself or another model). prime-radiant is **extrinsic** (fixed mathematical structure evaluating outputs against a known state graph).

**For BeKindRewindAI**: Each VHS tape's vocabulary/facts could be nodes in a sheaf. New transcriptions that contradict established facts would show high energy — detected without any LLM call.

---

## 5. What's the API — How Would Python Call This?

**CRITICAL FINDING**: The crate is `crate-type = ["rlib"]` only. **No PyO3, no WASM bindings.** Python cannot directly call this.

**Access patterns available**:

1. **Rust direct** (primary):
```rust
use prime_radiant::{CoherenceEngine, CoherenceConfig, CoherenceEnergy};
let engine = CoherenceEngine::new(CoherenceConfig::default());
engine.add_node("fact1", vec![1.0, 0.5, 0.3]);
engine.add_node("fact2", vec![0.9, 0.6, 0.2]);
engine.add_edge("fact1", "fact2", 1.0, None)?;
let energy = engine.compute_energy();
```

2. **Server binary** (if built): Could wrap in REST/gRPC API
3. **WASM** (feature `wasm` exists, but `crate-type` doesn't include `cdylib`)

**Python integration path** (hypothetical):
- mcporter (multi-language port toolchain used by RuVector ecosystem)
- PyO3 wrapper (needs to be written — not present)
- WASM via `wasm-bindgen` (not configured for library)

**ruvllm integration** (`examples/llm_validation.rs`):
```rust
// Shows coherence validation for LLM outputs
let validator = SheafCoherenceValidator::with_defaults();
let ctx = ValidationContext::new()
    .with_context_embedding(context_vec)
    .with_response_embedding(response_vec);
let result = validator.validate(&ctx)?;
if result.allowed { /* response passes */ }
```

---

## 6. Has Anyone Used This in Production?

**Finding: No publicly available production case studies.**

- **crates.io**: v0.1.0, first published 2026-01-23
- **GitHub stars**: Part of RuVector ecosystem (~3700 stars for main repo)
- **Author**: Reuven Cohen (RuVector team)
- **Literature**: arXiv paper "Prospects for inconsistency detection using large language models and sheaves" (Huntsman et al, 2024) — related academic work

**Related academic work**:
- "Sheaf theory: from deep geometry to deep learning" (arXiv:2502.15476)
- "A Gauge Theory of Superposition: Toward a Sheaf-Theoretic Atlas of Neural Representations" (arXiv:2603.00824)
- "Cohomological Obstructions to Global Counterfactuals" (arXiv:2603.17384)
- "Sheaves of Thought: Aligning LLM-RL Agents with Global Consistency" (Medium, 2025)

**Evidence of active development**: GitHub commits show active development through March 2026, feature additions, integration tests.

**Assessment**: This is a **new, experimental** crate. Production adoption is unconfirmed. The mathematical framework is sound (sheaf theory is well-established algebraic topology), but the specific implementations (restriction maps, energy thresholds) would need validation.

---

## Summary Table

| Aspect | Rating | Notes |
|--------|--------|-------|
| **Mathematical rigor** | High | Sheaf Laplacian is real algebraic topology |
| **Production maturity** | Low | v0.1.0, no public case studies |
| **Python accessibility** | None | Rust-only, no bindings |
| **Performance** | High | Sub-ms residuals, SIMD/GPU optional |
| **Novelty** | High | First sheaf-based hallucination detection in Rust |
| **BeKindRewindAI relevance** | Medium | Could model VHS memory graph, but no Python path |

---

## Key Files

- `src/coherence/engine.rs` — Core CoherenceEngine aggregate
- `src/coherence/energy.rs` — Energy formula: `E(S) = Σ(w_e * ||r_e||²)`
- `src/execution/ladder.rs` — 4-lane compute escalation
- `src/execution/gate.rs` — Threshold gating with witnesses
- `src/ruvllm_integration/coherence_validator.rs` — LLM output validation
- `src/substrate/mod.rs` — Sheaf graph data structures
