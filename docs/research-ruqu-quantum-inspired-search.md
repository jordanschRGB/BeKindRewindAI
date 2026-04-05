# RuQu Research: Quantum-Inspired Search Algorithms

## Executive Summary

**Short answer: ruQu is NOT a vector search competitor to HNSW. The speedup claims for vector search are theoretical and speculative — no implementation exists, no benchmarks against HNSW are provided, and the approach would likely be orders of magnitude slower than HNSW for any realistic workload.**

---

## 1. What "Quantum-Inspired" Means

**Classical quantum circuit simulation, NOT actual quantum hardware.**

The ruQu crates implement *classical simulators* of quantum algorithms. They run on standard CPUs/GPU via state-vector simulation, matrix multiplication, and tensor networks. There is zero quantum hardware involved.

- `ruqu-core` — 5 classical backends: StateVector (up to 32 qubits), Stabilizer (millions of qubits via Gottesman-Knill), Clifford+T, TensorNetwork, Hardware profiles
- `ruqu-algorithms` — VQE, Grover, QAOA, Surface Code algorithms built on top of ruqu-core
- `ruQu` — coherence gating: min-cut analysis for quantum hardware health monitoring (decide PERMIT/DEFER/DENY for quantum gate execution)

The "quantum-inspired" branding means: algorithms *inspired by* quantum computing research (Grover's quadratic speedup, QAOA's optimization landscape) are *simulated classically*.

---

## 2. Algorithms Implemented

### ruqu-algorithms (4 algorithms)

| Algorithm | Purpose | Speedup Claim |
|-----------|---------|---------------|
| **Grover's Search** | Unstructured search | O(√N) vs O(N) classical |
| **VQE** | Molecular ground states (chemistry) | Exponential for certain problems |
| **QAOA** | Combinatorial optimization (MaxCut) | Approximate advantage |
| **Surface Code** | Quantum error correction | Fault-tolerant computation |

### Grover's Search Implementation

From `grover.rs` in ruqu-algorithms, the algorithm:
1. Initializes uniform superposition over 2^n states
2. Applies O(√N) Grover iterations (oracle + diffuser)
3. Measures highest-probability state

```rust
// Optimal iterations: floor(π/4 * sqrt(N/k))
pub fn optimal_iterations(n_qubits: usize, n_marked: usize) -> usize
```

Key limitation: **Grover requires an oracle that can evaluate "is item i a match?" in O(1)**. For exact unstructured search (e.g., database with a matching record), this works. For *approximate* nearest neighbor search, distances are continuous — not a simple yes/no.

---

## 3. Speedup vs HNSW/IVF — The Claims

### The Speculative Hybrid Approach (ADR-QE-006)

The Architecture Decision Record proposes a two-phase approach:

```
Phase 1: Classical HNSW (coarse filtering)
  - Reduce search space from N to ~√N candidates
  - Time: O(log N)

Phase 2: Grover's Search (fine filtering)
  - Search among √N candidates
  - Quadratic speedup: O(√N) → O(N^(1/4))
  - Time: O(N^(1/4)) queries

Combined: O(log N + N^(1/4)) vs classical O(log N + √N)
```

### The Problem: This Is Theoretical

1. **No implementation exists.** The ADR is marked "Proposed" — not implemented.
2. **No benchmarks against HNSW.** Only internal Grover simulation benchmarks (e.g., 20 qubits = 1M states → ~500ms).
3. **The O(1) oracle assumption is broken for vector search.** Encoding a distance comparison as a Grover oracle requires iterating over all 2^n states to evaluate distances — negating the speedup.
4. **HNSW is already O(log N) for approximate search.** Grover's quadratic speedup applies to *unstructured* search (O(N) → O(√N)). HNSW is already sub-linear. The theoretical advantage disappears.

### Realistic Numbers

| Approach | N=1M | N=10M | N=1B |
|----------|------|-------|------|
| HNSW (ef_construction=200) | ~1ms | ~2ms | ~5ms |
| IVF (nlist=4096) | ~5ms | ~10ms | ~50ms |
| Grover (simulated, 20 qubits) | ~500ms | — | — |
| Grover + HNSW (theoretical) | ~500ms+ | — | — |

** Grover is 100-500x slower than HNSW for realistic workloads. The hybrid approach is slower than HNSW alone.**

---

## 4. Relationship to sparse-inference

**No direct relationship.** These are separate crates solving different problems.

| Crate | Purpose | Relationship |
|-------|---------|---------------|
| `ruvector-sparse-inference` | PowerInfer-style sparse neural network inference on edge devices | Separate; for LLM inference acceleration |
| `ruQu` | Quantum circuit simulation + coherence gating | Separate; for quantum algorithm prototyping |
| `ruqu-algorithms` | Grover/VQE/QAOA on classical simulators | Built on ruqu-core |
| `ruvector-core` (ruvector) | HNSW vector database | The actual vector search crate |

The only thin connection: Grover's algorithm *could theoretically* search over sparse vectors — but so could any linear scan. The overhead of state-vector simulation makes this impractical.

---

## 5. Could ruQu Replace or Augment HNSW for BeKindRewindAI?

**No. Three fundamental problems:**

### Problem 1: Grover is for Exact, Not Approximate Search
BeKindRewindAI uses approximate nearest neighbor search (ANN) — vectors are "close enough," not exact matches. Grover's oracle requires boolean match/no-match. Encoding continuous similarity scores as quantum oracles requires discretization that loses information and adds O(2^n) overhead per oracle call.

### Problem 2: Exponential Memory Scaling
State-vector simulation of n qubits requires 2^n complex numbers. At 20 qubits: 1M amplitudes ≈ 16MB. At 30 qubits: 1B amplitudes ≈ 16GB. HNSW operates on raw vectors with linear memory scaling.

### Problem 3: No Vector Index Structure
Grover assumes unstructured data — every item is equally likely to match. HNSW/IVF exploit geometric structure of vector spaces. Grover treats vectors as bitstrings — the metric is irrelevant to the algorithm.

**Verdict: Cannot replace HNSW. Cannot meaningfully augment it. The approach is a category error — mixing unstructured search theory with approximate vector geometry.**

---

## 6. Speedup Claims — Are They Real?

### For Unstructured Search: Yes, Theoretically
Grover provides genuine O(√N) vs O(N) speedup for finding exact matches in unstructured databases. This is a proven quantum algorithm result.

**But:**
- The database must support O(1) oracle evaluation
- The data must be truly unstructured (no geometric prior)
- RuVector's implementation is classical simulation — no actual quantum advantage

### For Vector Search: No
- HNSW already achieves O(log N) via graph navigation — already sub-linear
- Grover's speedup applies to linear-time unstructured search, not logarithmic-time graph search
- The hybrid proposal is theoretical, unimplemented, and would be slower than HNSW alone
- No benchmarks exist comparing Grover-based search to HNSW

### RuQu's Own Benchmarks (from README)
These are for quantum circuit simulation, NOT vector search:
- Grover (N=1024, 10 qubits): 15ms
- VQE (H2, 4 qubits): 50ms/iteration
- QAOA (depth=3, 8 qubits): 100ms

**None of these are vector search benchmarks.**

---

## 7. Summary Table

| Question | Answer |
|----------|--------|
| "Quantum-inspired" means actual quantum hardware? | **No** — classical simulation only |
| What algorithms does ruQu implement? | Grover's, VQE, QAOA, Surface Code |
| What's faster vs HNSW? | **Nothing.** The hybrid approach is theoretical, unimplemented, and would be slower. |
| Relation to sparse-inference? | **None.** Separate crates solving different problems. |
| Could it replace HNSW for memory search? | **No.** Category error — exact unstructured search vs approximate geometric search. |
| Are speedup claims real? | For unstructured exact search: theoretically yes. For vector search: **no evidence, likely slower.** |

---

## 8. Recommendation for BeKindRewindAI

**Drop ruQu from consideration for memory search.** 

Jordan's flag was reasonable to investigate, but the speedups are not real for the vector search use case. The "quantum-inspired" branding is misleading — this is a quantum circuit simulator, not a faster ANN algorithm.

If BeKindRewindAI needs faster memory search:
- Current HNSW/IVF approach is appropriate
- Consider `ruvector-core` for a well-optimized Rust HNSW implementation
- Consider `ruvector-sparse-inference` for efficient LLM inference with sparse activations
- Consider `ruvector-delta-core` for temporal/versioned vector storage

ruQu is interesting for quantum algorithm *prototyping* and *education*, but not for production vector search workloads.
