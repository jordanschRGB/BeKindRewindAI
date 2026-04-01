# Research: graph-transformer — Hyperbolic Graph Indexing

## TL;DR

`ruvector-graph-transformer` is **NOT** a hyperbolic graph indexing crate. It's a proof-gated GNN with 8 orthogonal modules. The actual hyperbolic indexing crate is `ruvector-hyperbolic-hnsw`. Neither has Python bindings. Hyperbolic indexing helps only with hierarchical memory structures — low relevance for Dreamer's flat HNSW unless memory is restructured as a taxonomy.

---

## 1. What Hyperbolic Graph Indexing Means Practically

### Two Relevant Crates

| Crate | Purpose | Hyperbolic Role |
|-------|---------|-----------------|
| `ruvector-graph-transformer` | Proof-gated GNN with 8 modules | One module via `manifold` feature |
| `ruvector-hyperbolic-hnsw` | Hyperbolic vector indexing + HNSW | Core feature |

### `ruvector-graph-transformer` (NOT hyperbolic indexing)

Eight independent modules:

| Module | Feature Flag | Purpose |
|--------|-------------|---------|
| Proof-Gated Mutation | (always on) | Every mutation requires formal proof |
| Sublinear Attention | `sublinear` | O(n log n) attention via LSH/PPR/spectral |
| Physics-Informed | `physics` | Hamiltonian dynamics, energy conservation |
| Biological | `biological` | Spiking attention, Hebbian/STDP learning |
| Self-Organizing | `self-organizing` | Morphogenetic fields |
| **Manifold** | `manifold` | Product manifolds S^n x H^m x R^k |
| Temporal-Causal | `temporal` | Causal masking, Granger causality |
| Economic | `economic` | Nash equilibrium, Shapley attribution |

The `manifold` feature routes attention heads to spherical (S^n), hyperbolic (H^m), or Euclidean (R^k) spaces via `CurvatureAdaptiveRouter` using Ollivier-Ricci curvature.

### `ruvector-hyperbolic-hnsw` (Actual Hyperbolic Indexing)

Implements the **Poincaré ball model** — a hyperbolic space representation where distance grows exponentially near the boundary:

```rust
// Möbius addition (hyperbolic vector addition)
let z = mobius_add(&x, &y, c);

// Geodesic distance
let d = poincare_distance(&x, &y, c);

// Exponential map (tangent space → manifold)
let y_recovered = exp_map(&v, &x, c);

// Logarithmic map (manifold → tangent space)
let v = log_map(&y, &x, c);
```

Key design:
- **Tangent space pruning**: Precomputes `u = log_c(x)` at shard centroid, uses Euclidean distance to prune candidates before exact hyperbolic ranking
- **Per-shard curvature**: Different hierarchy levels can have different optimal curvatures
- **Dual-space index**: Synchronized Euclidean ANN for fallback and mutual-ranking fusion
- **HNSW integration**: Graph-based k-NN search on hyperbolic embeddings

### Why Hyperbolic Space?

Hierarchical data (trees, taxonomies, ontologies) compress naturally in hyperbolic space with near-zero distortion using O(n) dimensions. Euclidean space assumes uniform curvature; hyperbolic handles hierarchical/taxonomic data much better.

---

## 2. Memory/Vocabulary Organization

### What This Could Help With

- **Hierarchical memory schemas**: WordNet-like taxonomies, topic hierarchies compress well in hyperbolic space
- **Taxonomy-aware recall**: Hyperbolic HNSW naturally groups hierarchical concepts closer together
- **Deep-leaf recall**: Long-tail concepts (rare vocabulary) preserved without distortion
- **Concept hierarchies**: Animal → Mammal → Dog → Golden Retriever preserves distances at all scales

### What It Would NOT Help With

- **Flat vocabulary lists**: No hierarchy to exploit
- **Sequential/contextual memory**: Temporal-causal attention is separate module
- **Real-time transcription memory**: Whisper uses CTC (not transformer attention)

### Integration Path for Dreamer

1. Restructure VHS memory as hierarchical taxonomy (Episode → Character → Location → Scene)
2. Use `ruvector-hyperbolic-hnsw` for storing/retrieving embeddings
3. Build custom PyO3 wrapper or use subprocess via `ruvector-cli`
4. Query by hierarchical concept: "all animal-related vocabulary"

---

## 3. Benchmarks vs Flat or Tree-Based Structures

### For `ruvector-hyperbolic-hnsw`

Criterion benchmark suite exists at `benches/hyperbolic_bench`:
- Poincaré distance computation
- Möbius addition
- exp/log map operations
- HNSW insert and search
- Tangent cache building
- Search with vs without pruning

### Theoretical Comparisons

| Structure | Hyperbolic HNSW | Euclidean HNSW | Tree-Based (Annoy) |
|-----------|-----------------|---------------|-------------------|
| Hierarchical data recall | **Best** | Good | Medium |
| Recall @k | High | High | Lower |
| Query latency | Comparable | Comparable | Faster |
| Memory overhead | Slightly higher | Standard | Lower |
| Curvature adaptation | Per-shard | N/A | N/A |

**Key tradeoff**: Hyperbolic provides better recall for hierarchical data but adds computational overhead for Möbius operations. For flat data, no advantage over Euclidean HNSW.

---

## 4. Python Bindings

**None exist for either crate.**

| Crate | Python | WASM | Node.js | Native Rust |
|-------|--------|------|---------|-------------|
| `ruvector-graph-transformer` | No | Yes | Yes (NAPI-RS) | Yes |
| `ruvector-hyperbolic-hnsw` | No | Yes | No | Yes |

### Python Access Paths

1. **`ruvector-cli` subprocess wrapper**: CLI commands for insert/search
2. **`ruvector-server` HTTP REST API**: Docker container with REST endpoints
3. **Custom PyO3 bindings**: Roll your own (not provided by RuVector)

---

## 5. Could This Improve Dreamer's Memory Recall?

### Assessment: **Low Direct Relevance**

**Why:**
1. **No Python bindings** — requires wrapper overhead (subprocess or custom PyO3)
2. **Hyperbolic benefits only for hierarchical data** — Dreamer's flat HNSW has no taxonomy to exploit
3. **Whisper uses CTC transcription** — not transformer attention, so graph-transformer modules don't apply
4. **Integration cost is high** — restructuring memory schema, building wrappers, no production validation

### If Restructuring Memory as Hierarchy

**Medium relevance** if:
- VHS memories are recast as Episode/Character/Location nodes with temporal/scene edges
- `ruvector-graph` (graph DB layer) is used instead of flat HNSW
- Custom Python wrapper built around `ruvector-hyperbolic-hnsw`

### Alternative: `ruvector-graph` Crate

The `ruvector-graph` crate (v2.0.6) layers a Neo4j-compatible property graph + Cypher + GNN on top of flat HNSW. VHS memories model naturally as a graph:
- Episode/Character/Location nodes
- `temporal_next`/`scene` hyperedges for co-occurrence
- GraphDB CRUD, full Cypher parser, hybrid vector-graph queries

This is a better fit than `graph-transformer` for memory organization since it doesn't require hyperbolic geometry — just structured relationships.

---

## Crate Metadata

| | `ruvector-graph-transformer` | `ruvector-hyperbolic-hnsw` |
|--|------------------------------|---------------------------|
| **Version** | ? | 0.1.0 |
| **Location** | `crates/ruvector-graph-transformer` | `crates/ruvector-hyperbolic-hnsw` |
| **Primary purpose** | Proof-gated GNN | Hyperbolic vector indexing |
| **Hyperbolic geometry** | Via `manifold` feature only | Core feature |
| **HNSW integration** | No | Yes |
| **Python bindings** | No | No |
| **WASM bindings** | Yes | Yes |
| **Tests** | 186 passing | Criterion benchmarks |
| **Dependencies** | ruvector-verified, ruvector-gnn, ruvector-attention, ruvector-mincut, ruvector-solver, ruvector-coherence | nalgebra, ndarray, rayon, serde, rand |
