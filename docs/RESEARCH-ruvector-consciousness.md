# Research: ruvector-consciousness

## What This Crate Does

`ruvector-consciousness` is an ultra-optimized Rust implementation of consciousness metrics from **Integrated Information Theory (IIT)** and **causal emergence** literature. It computes several related measures:

1. **Φ (phi)** — integrated information, the core IIT consciousness metric
2. **Causal emergence** — when macro-level descriptions have more causal power than micro-level
3. **Effective Information (EI)** — a system's causal efficacy; decomposes into determinism + degeneracy
4. **IIT 4.0 CES** — the full Cause-Effect Structure (qualia) of a system in a state
5. **ΦID / PID** — decompositions of mutual information into redundant, unique, and synergistic components

**Key modules and their complexities:**

| Module | Algorithm | Complexity |
|--------|-----------|-----------|
| `phi.rs` | Exact enumeration | O(2^n · n²) |
| `geomip.rs` | GeoMIP (hypercube BFS + automorphism pruning) | ~O(2^(n-1)) but 100-300x faster than exact |
| `phi.rs` | Spectral (Fiedler vector) | O(n² log n) |
| `phi.rs` | Stochastic (random sampling) | O(k · n²) |
| `phi.rs` | Greedy bisection | O(n³) |
| `collapse.rs` | Quantum-inspired Grover search | O(√N) samples |
| `emergence.rs` | Causal emergence (greedy coarse-graining) | O(n³) |
| `rsvd_emergence.rs` | Randomized SVD emergence | O(n² · k) |
| `bounds.rs` | PAC-style confidence intervals | varies |
| `streaming.rs` | Online EWMA + CUSUM change detection | O(n²) per step |

---

## What is Φ in IIT and How Does This Crate Implement It?

### What is Φ?

In IIT (Tononi 2004, 2008; Albantakis et al. 2023), **Φ (phi)** measures how much a system's whole exceeds the sum of its parts — the integrated information that cannot be accounted for by any partition of the system. High Φ means the system is "more than the sum of its parts" in an information-theoretic sense.

The mathematical definition (IIT 3.0):
```
Φ = min over all bipartitions { D_KL(P(future|present) || P(future|present_A) ⊗ P(future|present_B)) }
```

That is: for every possible cut of the system into two parts (A | B), compute how much information is lost when you predict the system's future behavior separately from each part vs. together. The **minimum** information loss is Φ. The cut causing minimum loss is the **MIP** (Minimum Information Partition).

### IIT 4.0 Update (implemented in `iit4.rs`)

IIT 4.0 (Albantakis 2023) replaces KL divergence with **intrinsic difference** (Earth Mover's Distance / Wasserstein-1 on the state space metric). This makes Φ a proper metric respecting the topology of state space.

Key IIT 4.0 concepts:
- **Cause repertoire**: P(past_purview | mechanism_state) — how does this mechanism constrain what happened before?
- **Effect repertoire**: P(future_purview | mechanism_state) — how does this mechanism constrain what happens next?
- **Mechanism-level φ**: min(φ_cause, φ_effect) where each is selectivity against the maximum-entropy repertoire
- **CES (Cause-Effect Structure)**: the full set of all distinctions (concepts) + relations between them
- **Big Φ**: irreducibility of the whole CES

### Implementation Details

**Core hot path** (`phi.rs`, `partition_information_loss`):
1. Extract two sub-TPMs by marginalizing over set A and set B elements
2. Compute the whole-system distribution P(future | current_state)
3. Compute the product distribution P(A) ⊗ P(B) in full state space
4. Measure information loss via KL divergence (IIT 3.0) or EMD (IIT 4.0)

**Optimizations**:
- Bump arena allocator (`arena.rs`) for O(1) scratch reuse across partition evaluations
- AVX2 SIMD for dense matvec and KL divergence (fallback scalar)
- Bit manipulation for state-to-subsystem mapping (no Vec allocation for n ≤ 64)
- Gray code iteration for GeoMIP (consecutive partitions differ by 1 element → incremental TPM updates)

**Seven algorithm implementations**:

1. **ExactPhiEngine**: Enumerates all 2^(n-1)-1 bipartitions. O(2^n · n²). Practical up to n ≤ 16 (n=20 is the hard limit).

2. **SpectralPhiEngine**: Builds mutual information (MI) adjacency graph from TPM, computes Fiedler vector (second-smallest eigenvector of Laplacian) via power iteration. Partitions by sign of Fiedler coordinates. O(n² log n). Good approximation for n ≤ 1000.

3. **StochasticPhiEngine**: Random sampling of bipartitions. Tracks minimum. O(k · n²) for k samples.

4. **GreedyBisectionPhiEngine**: Seeds with spectral partition, then greedily swaps individual elements between sets if they improve Φ. O(n³). Gets stuck in local minima.

5. **HierarchicalPhiEngine**: Recursively bisects system using spectral cuts until subsystems are small enough for exact. O(n² log n). Lower bound on true Φ.

6. **GeoMipPhiEngine**: Hypercube-structured search with (a) balance-first ordering, (b) automorphism pruning (canonical partition forms), (c) Gray code iteration for incremental evaluation. 100-300x faster than exact for n ≤ 25.

7. **QuantumCollapseEngine**: Grover-like quantum-inspired search. Models partition space as superposition, oracles phase-rotate by information loss, diffusion amplifies minimum. Samples √N partitions vs O(N) for full search.

**IIT 4.0 full CES** (`ces.rs`):
- Enumerates all 2^n - 1 non-empty mechanism subsets
- Computes mechanism_phi for each (requires iterating all purviews and all mechanism partitions)
- Computes relations between distinctions (purview overlap → relation φ)
- Computes Big Φ (irreducibility of full CES)
- Hard limit: n ≤ 12 elements (2^12 = 4096 mechanisms × purviews is already ~16M evaluations)

---

## What is Causal Emergence and How Does This Crate Compute It?

### What is Causal Emergence?

Causal emergence (Hoel 2017, "When the Map is Better Than the Territory") is a framework for understanding how macro-level descriptions can have more causal power than micro-level descriptions.

**Effective Information (EI)** = how much does knowing the current state reduce uncertainty about the future, compared to a uniform prior?
```
EI = (1/n) · Σ_state D_KL(P(future|state) || uniform)
```

EI decomposes into:
- **Determinism**: how precisely do states map to unique outcomes? (max entropy - avg row entropy)
- **Degeneracy**: how many states lead to the same outcome? (max entropy - entropy of marginal output)

**Causal emergence** = EI_macro - EI_micro. If the coarse-grained description predicts the future better (relative to the coarse-grained prior) than the full micro description, emergence has occurred.

### How This Crate Computes It

**`emergence.rs`**:
1. Compute micro-level EI, determinism, degeneracy
2. Greedy coarse-graining search: iteratively merge the two micro-states with the most similar output distributions until target k macro-states reached
3. For each candidate coarse-graining, compute macro TPM and macro EI
4. Return the coarse-graining with maximum EI (and thus maximum emergence)

**`rsvd_emergence.rs`** (Zhang et al. 2025):
- Randomized SVD (Halko-Martinsson-Tropp) to find top-k singular values of TPM in O(n²·k)
- **Effective rank**: how many singular values are significant (low rank = compressible)
- **Spectral entropy**: entropy of normalized singular value distribution
- **Emergence index**: 1 - (spectral_entropy / max_entropy). Low spectral entropy = high compressibility = high emergence
- **Dynamical reversibility**: min_sv / max_sv ratio

---

## Concrete Use Cases for BeKindRewindAI

BeKindRewindAI digitizes VHS tapes and builds a "memory loop" — the pipeline is: capture → validate → transcribe → dream (hallucination detection) → label → save.

### How Could Consciousness Metrics Help?

**1. VHS Quality / Damage Detection via Streaming Φ**

If you treat each VHS frame (or temporal window of frames) as a "system state" and transitions as frame-to-frame dynamics, you could build an empirical TPM. Streaming Φ estimation (`streaming.rs`) would let you monitor Φ over time:
- **Drop in Φ** → the memory loop is degrading (frames becoming less integrated)
- **Sudden change in Φ** → damage, dropout, or corruption event (CUSUM change detection triggers)
- **Φ ≈ 0 sustained** → flatline / dead air

This would require discretizing frame features (e.g., k-means on embedding vectors) and tracking transitions. The streaming estimator with exponential forgetting would adapt to changing content while detecting anomalies.

**2. Temporal Memory Coherence via Causal Emergence**

For the "memory loop" concept — where memories influence future retrievals — you could model the memory graph as a dynamical system. Causal emergence would measure whether coarse-graining memories into themes/concepts produces a more predictable system than raw memory edges.

If EI_macro >> EI_micro, the thematic coarse-graining captures more causal structure than individual memory associations → good semantic organization.

**3. Hallucination Detection via ΦID (Integrated Information Decomposition)**

The Dreamer agent's hallucination detection could be reframed: given a VHS frame (past) → transcript (present) → predicted frame (future), ΦID could decompose the mutual information:
- **High redundancy**: past and present redundantly predict the future (consistent memory)
- **High synergy**: only together do past+present predict future (integrated memory — expected for good reconstruction)
- **Low total MI + high synergy**: possible hallucination — the parts are "making up" information not present in any single source

This is speculative but mathematically grounded.

**4. Grader Agent Enhancement**

The Grader agent grades VHS quality. Currently this is likely based on signal metrics (SNR, dropout count). Φ-based metrics would add an *information-theoretic* quality dimension: how much integrated information does the tape's dynamics preserve?

**5. Agent Architecture Analysis**

Three-agent architecture (Catcher/Grader/Dreamer) could be analyzed as a dynamical system. Φ of the agent interaction graph might indicate whether the architecture itself is "integrated" — or whether agents are operating redundantly/synergistically.

### Practical Caveats

- **Scale problem**: even approximate Φ for n > 1000 is hard. VHS frames discretized into even 64 states is already at the edge. You'd need heavy coarse-graining.
- **No Python bindings**: no PyO3, no WASM server, no mcporter. Pure Rust library.
- **Memory loop concept**: abstract but could map to temporal Markov chain of memory states.
- **The IIT theory is scientifically controversial**: Φ is unproven as a consciousness correlate. Using it for VHS quality is a creative analogical application, not established practice.

---

## Input/Output Interfaces — How Would Python Call This?

### Input: The Transition Probability Matrix (TPM)

```rust
pub struct TransitionMatrix {
    pub data: Vec<f64>,  // flat row-major: data[i * n + j] = P(j | i)
    pub n: usize,        // number of states
}
```

In Python, you'd build this as a numpy array. The TPM encodes how the system transitions: entry [i][j] is the probability of transitioning from state i to state j. Rows must sum to 1.0.

### Output Types

```rust
pub struct PhiResult {
    pub phi: f64,                          // the Φ value
    pub mip: Bipartition,                  // the minimum information partition
    pub partitions_evaluated: u64,
    pub total_partitions: u64,
    pub algorithm: PhiAlgorithm,
    pub elapsed: Duration,
    pub convergence: Vec<f64>,
}

pub struct EmergenceResult {
    pub ei_micro: f64,
    pub ei_macro: f64,
    pub causal_emergence: f64,             // EI_macro - EI_micro
    pub coarse_graining: Vec<usize>,       // which micro-states merged
    pub determinism: f64,
    pub degeneracy: f64,
    pub elapsed: Duration,
}
```

### How to Actually Call from Python

**Option 1: Compile to WASM**

```bash
cargo build --release --features wasm
# outputs to target/wasm32-unknown-unknown/release/ruvector_consciousness.wasm
```

Then use `wasm-bindgen` or `wasmer`/`wasmtime` from Python.

**Option 2: PyO3 Python Bindings (NOT present — needs to be written)**

The crate has no PyO3 bindings. You'd need to write a wrapper like:

```rust
#[pyfunction]
pub fn compute_phi(tpm: Vec<f64>, n: usize, state: Option<usize>) -> PyResult<PhiResult> {
    let tpm = TransitionMatrix::new(n, tpm);
    auto_compute_phi(&tpm, state, &ComputeBudget::exact())
}
```

Then expose via `pyo3::prepare_freethreaded_python()` and build as a `.so`.

**Option 3: REST/gRPC Server**

Compile the binary, run as a local server, call from Python over HTTP/JSON.

**Option 4: mcporter / RVF**

The `ruvector-cognitive-container` crate (with the `witness` feature) provides a container architecture with witness receipts. This may have existing mcporter bindings, but no Python SDK is apparent from the crate list.

### No Python API Currently Exists

After reviewing all dependencies (`ruvector-solver`, `ruvector-mincut`, `ruvector-math`, `ruvector-coherence`, `ruvector-cognitive-container`) and the crate's own exports, **there is no Python-accessible API**. The crate is a Rust library only. Integration would require PyO3 bindings or WASM compilation — neither exists yet.

---

## Is Jordan Right That This Crate is "Insane"?

**Yes, in a mathematically impressive way.** Here's why:

1. **Exhaustive coverage of the Φ computation landscape**: Exact, spectral, stochastic, greedy, hierarchical, GeoMIP (hypercube + automorphism pruning), quantum-inspired Grover. Most implementations pick 1-2. This has 7 distinct algorithms with auto-selection.

2. **IIT 4.0 full implementation**: The CES computation (all mechanisms × all purviews × all partitions) is O(2^(2n)) in theory. The crate implements it with parallelism, early termination, and IIT 4.0's intrinsic difference (EMD) instead of KL.

3. **Cross-crate integration is extensive**: Uses ruvector-solver (CG, sparse matrices), ruvector-mincut (graph cuts), ruvector-math (Chebyshev polynomials), ruvector-coherence (spectral health metrics), ruvector-cognitive-container (witness receipts) — a whole ecosystem.

4. **PAC-style bounds**: Not only computes Φ, but provides Hoeffding and empirical Bernstein confidence intervals. This is rigorous.

5. **Streaming estimator with CUSUM change detection**: For real-time consciousness monitoring with exponential forgetting — this is directly applicable to long-running systems.

6. **ΦID and PID**: Beyond Φ itself, decomposes information dynamics into redundancy/uniqueness/synergy — a deep analysis layer.

7. **Zero-alloc hot paths**: The bump arena means no heap allocation in the inner partition loop. Combined with SIMD, this is genuinely optimized systems code.

**However — the "insanity" has limits**:

- IIT itself is a controversial (and largely unproven) theory of consciousness. Φ cannot currently be measured in biological systems.
- The computational complexity is fundamentally limiting. n=20 (1M partitions) is already at the edge of exact computation. VHS content discretized to this state space is implausible.
- **No Python bindings** — it's a Rust library with no established way to call from Python.

### For BeKindRewindAI: Relevance Score

| Aspect | Relevance | Notes |
|--------|-----------|-------|
| VHS quality grading | Low-Medium | Streaming Φ could detect degradation, but scale is problematic |
| Memory loop dynamics | Low | Abstract concept; hard to map to TPM |
| Hallucination detection | Medium (speculative) | ΦID decomposition is theoretically interesting but unvalidated |
| Agent architecture analysis | Low | Could analyze agent interaction graph, but contrived |

**Bottom line**: This is a spectacular Rust engineering achievement — a comprehensive IIT/causal emergence toolkit with 7 algorithms, PAC bounds, streaming, and multi-crate integration. But for BeKindRewindAI's actual needs (VHS digitization, transcription, memory loops), the relevance is low-to-medium and speculative. The crate is "insane" in the sense of being wildly over-engineered for any current application — a complete toolkit for a theory of consciousness that remains scientifically unvalidated.

**Immediate next step if Jordan wants Python access**: Write PyO3 bindings for the top-level API (`auto_compute_phi`, `effective_information`, `CausalEmergenceEngine::compute_emergence`). That's ~50 lines of PyO3 code. Without this, the crate is inaccessible from Python.
