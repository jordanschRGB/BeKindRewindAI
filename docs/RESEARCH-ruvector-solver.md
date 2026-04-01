# Research: ruvector-solver

## 1. What kind of solver is this?

**Sparse iterative linear solvers** — NOT SAT/SMT/CSP/ILP. This crate solves sparse linear systems `Ax = b` and Personalized PageRank (PPR) on sparse graphs. The matrix `A` is stored in CSR (Compressed Sparse Row) format. It does not solve constraint satisfaction, boolean formulas, or integer programs.

Core problem classes:
- `Ax = b` for diagonally dominant / SPD sparse matrices (Neumann, CG, BMSSP)
- Personalized PageRank from single/multiple seed nodes (Forward Push, Backward Push, Hybrid Random Walk)
- Spectral graph filtering via polynomial expansion
- Batch linear systems sharing the same matrix `A` (TRUE solver)

## 2. Algorithms

Seven sparse algorithms available behind feature flags:

| Algorithm | Module | Complexity | When to Use |
|-----------|--------|------------|-------------|
| **Neumann Series** | `neumann` | O(nnz * log(1/eps)) | Diagonally dominant, very sparse matrices. Jacobi-preconditioned iteration `x_{k+1} = x_k + D^{-1}(b - Ax_k)`. Requires spectral radius < 1. |
| **Conjugate Gradient (Hestenes-Stiefel)** | `cg` | O(nnz * sqrt(kappa)) | Symmetric positive-definite (SPD) matrices. Optimal for well-conditioned systems. |
| **Forward Push** (Andersen-Chung-Lang) | `forward_push` | O(1/epsilon) sublinear | Single-source PPR. Push residual mass along edges until residuals fall below threshold. |
| **Backward Push** | `backward_push` | O(1/epsilon) sublinear | Target-centric PPR — reverse relevance from a target node. |
| **Hybrid Random Walk** | `random_walk` | O(sqrt(n)/epsilon) | Large-graph PPR where pure push is too expensive. Combines push initialization with Monte Carlo sampling. |
| **TRUE** (Topology-aware Reduction for Updating Equations) | `true_solver` | O(nnz * log n) | Batch linear systems with shared matrix `A` — amortizes factorization across RHS vectors. |
| **BMSSP** (Block Maximum Spanning Subgraph Preconditioner) | `bmssp` | O(n log n) | Ill-conditioned systems and graph Laplacians where CG and Neumann both struggle. V-cycle multigrid with Jacobi smoothing. |

Key implementation details:
- **AVX2 SIMD SpMV**: 8-wide vectorized sparse matrix-vector multiply via `_mm256` intrinsics
- **Fused residual + norm**: Computes `r = b - Ax` and `||r||^2` in a single memory pass (3x reduction in memory traffic)
- **4-wide unrolled Jacobi update**: ILP-optimized inner loop
- **Arena allocator**: Bump allocation for zero per-iteration heap overhead
- **Fallback chain**: selected → CG → Dense (guaranteed convergence)

## 3. Key API Entry Points

```rust
// Core type: CSR matrix
use ruvector_solver::types::CsrMatrix;
let a = CsrMatrix::<f64>::from_coo(rows, cols, vec![(i, j, val), ...]);

// Direct solver usage
use ruvector_solver::neumann::NeumannSolver;
let solver = NeumannSolver::new(1e-6, 500);
let result = solver.solve(&matrix, &rhs).unwrap();

// Automatic routing
use ruvector_solver::router::{SolverRouter, SolverOrchestrator, QueryType};
let orchestrator = SolverOrchestrator::new(RouterConfig::default());
let result = orchestrator.solve(&matrix, &rhs, QueryType::LinearSystem, &budget).unwrap();

// PageRank (sublinear)
use ruvector_solver::forward_push::ForwardPushSolver;
let solver = ForwardPushSolver::new(0.85, 1e-6); // alpha, epsilon
let ppr = solver.ppr(&graph, source_node, 0.85, 1e-6).unwrap(); // returns Vec<(node, score)>
```

Core traits:
- `SolverEngine::solve(&self, matrix, rhs, budget) -> SolverResult`
- `SublinearPageRank::ppr(matrix, source, alpha, epsilon) -> Vec<(usize, f64)>`
- `SparseLaplacianSolver::solve_laplacian()` + `effective_resistance()`

## 4. BeKindRewindAI Relevance

### Grader Agent (VHS Quality Scoring)

**Could it help? Indirectly, low immediate relevance.**

The Grader scores VHS quality based on signal noise, distortion, dropout events, color bleed, etc. This is a classification/regression problem — not a linear system solve.

However, the Forward Push PPR algorithm could model **semantic proximity** between quality artifacts. If quality issues are encoded as nodes in a graph (e.g., "color_bleed", "audio_dropout", "tracking_error") and their co-occurrence forms edges weighted by frequency, PPR could identify which artifact clusters tend to appear together — helping the Grader prioritize which defects dominate the quality score.

A more direct application: if the Grader builds a **co-occurrence matrix** of defects across many VHS samples, the Neumann or CG solver could solve a linear system that propagates confidence scores across the defect graph.

### Dreamer Agent (Hallucination Detection)

**Could help — moderate relevance, primarily via the SublinearPageRank interface.**

Memory coherence in BeKindRewindAI involves detecting when a memory narrative conflicts with itself (hallucination). The solver could model **semantic memory as a graph** where:
- Nodes = memory fragments / entities
- Edges = temporal or causal relationships
- Edge weights = coherence strength

Running PPR from a "query memory" would identify which related memories are most activated — if activated memories are semantically inconsistent (e.g., a person appearing in two contradictory events), those become hallucination candidates. The `SublinearPageRank::ppr_multi_seed()` method handles multiple seed nodes, which maps naturally to evaluating coherence across multiple memory threads simultaneously.

The `SolverOrchestrator::analyze_sparsity()` could also detect **structural anomalies** in the memory graph — a memory graph where certain nodes have abnormally high connectivity (memory hubs) might indicate confabulation.

### Summary Assessment

| Agent | Relevance | Mechanism |
|-------|-----------|-----------|
| Grader | Low | PPR-based artifact co-occurrence clustering |
| Dreamer | Moderate | Sublinear PPR for memory coherence queries; graph structural analysis |

The primary blocker for both: **BeKindRewindAI would need to first build a graph structure** from VHS memories. Currently it uses flat files. The solver doesn't help without a graph.

## 5. Python Access

**No direct Python bindings.** This is a pure Rust library with no PyO3, ctypes, or C extension bindings. Available access paths:

1. **WASM** (`wasm` feature): The crate has `wasm-bindgen` bindings and can run in a browser or via Pyodide/WASM Python environments (e.g., `python-wasm`).

2. **mcporter**: RuVector's binary transport layer. If `ruvector-solver` is exposed via mcporter, Python could call it through that RPC mechanism. Check if the mcporter crate exposes solver functions.

3. **Rust binary + subprocess**: Compile the solver as a standalone binary and invoke via `subprocess.run()` from Python, passing CSR matrix data as JSON/msgpack and receiving results back.

4. **PyO3 wrapper**: Someone would need to write a `ruvector-solver-py` crate using PyO3 to expose the API to Python directly. This is not currently present.

The README mentions "Full wasm-bindgen bindings" and "Run solvers in the browser" but does not mention any Python SDK or PyO3 bindings. For BeKindRewindAI to use this from Python, a PyO3 wrapper or mcporter integration would need to be built.

## Summary

ruvector-solver is a high-performance sparse linear algebra library with seven specialized algorithms achieving O(log n) to O(sqrt(n)) complexity. Its strongest BeKindRewindAI application is **SublinearPageRank** for memory coherence queries — if the Dreamer builds a semantic memory graph, PPR could rank which memories are most contextually relevant and detect structural anomalies. The Grader could use artifact co-occurrence matrices + linear solves for defect propagation, but this requires more architectural investment. Python access requires WASM, mcporter, or a new PyO3 wrapper.
