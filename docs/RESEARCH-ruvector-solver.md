# Research: ruvector-solver — Sublinear Solvers

**Bead**: 095b3292-40e2-4117-ab0a-beda4bbcaf9b
**Date**: 2026-04-01
**Agent**: Dusk-polecat-63341274@28eb9c76

## What It Does

ruvector-solver is a Rust crate providing 7 sparse matrix algorithms with O(log n) to O(sqrt(n)) complexity, dramatically faster than dense O(n^3) solvers like nalgebra for large systems. The core abstraction is a `CsrMatrix<T>` (compressed sparse row) that only stores non-zero entries.

## Algorithms Implemented

| Algorithm | Complexity | Use Case |
|-----------|-----------|----------|
| Jacobi-preconditioned Neumann series | O(nnz * log(1/eps)) | Diagonally dominant Ax=b |
| Conjugate Gradient (Hestenes-Stiefel) | O(nnz * sqrt(kappa)) | Symmetric positive-definite Ax=b |
| Forward Push (Andersen-Chung-Lang) | O(1/epsilon) | Single-source Personalized PageRank |
| Backward Push | O(1/epsilon) | Reverse relevance / target-centric PPR |
| Hybrid Random Walk | O(sqrt(n)/epsilon) | Large-graph PPR with push init |
| TRUE (JL + sparsification + Neumann) | O(nnz * log n) | Batch linear systems with shared A |
| BMSSP Multigrid (V-cycle + Jacobi) | O(n log n) | Ill-conditioned / graph Laplacian |

## Key Technical Features

- **AVX2 8-wide SIMD SpMV**: bounds-check-free inner loops, 3x fused residual+norm pass
- **SolverRouter**: automatically picks the optimal algorithm from 7 based on matrix structure
- **Fallback chain**: selected → CG → dense, ensuring convergence in production
- **ComputeBudget**: enforces max time, iterations, and tolerance per solve
- **WASM support**: full wasm-bindgen bindings for browser execution
- **177 tests** with Criterion benchmarks (solver_neumann, solver_cg, solver_push, solver_e2e)

## Sublinear PageRank

The 3 PPR algorithms (Forward Push, Backward Push, Hybrid Random Walk) compute Personalized PageRank in O(1/epsilon) to O(sqrt(n)/epsilon) time — **not** O(n) or O(n log n) like naive power iteration. The `SublinearPageRank` trait exposes `ppr(matrix, source, alpha, epsilon)`.

## Python Accessibility

**Not directly accessible from Python.** No PyO3 bindings, no mcporter mention in the README. The crate is pure Rust with optional WASM — Python would need PyO3 wrappers built separately. RuVector's mcporter API likely wraps this internally, but the solver itself is not exposed as a standalone Python library.

## Relevance to BeKindRewindAI

**Low-to-medium relevance for ranking/vocabulary scoring.** The sublinear PPR algorithms could rank vocabulary items by relevance or importance across a tape corpus — useful if BeKindRewindAI ever scales to thousands of tapes with a graph of term co-occurrence. However, the current system stores vocabulary in flat files, uses no graph structures, and has no ranking requirements that justify this complexity. The conjugate gradient solver could accelerate normal equations for least-squares fitting of embedding models, but that's speculative. The primary value is conceptual: understanding that sublinear solvers exist could inform future architecture decisions if the vocabulary graph grows large enough to warrant graph-analytics infrastructure.

## Summary

ruvector-solver is a well-engineered Rust library for sparse linear systems and sublinear PageRank. It is **not** a drop-in Python library — it needs PyO3 bindings to be callable from Python. For BeKindRewindAI at its current scale, flat files + simple scoring are more appropriate. But if vocabulary grows into a large co-occurrence graph (thousands of terms across hundreds of tapes), PPR-based ranking via this crate could become genuinely useful. Watch this crate if the vocabulary system scales.
