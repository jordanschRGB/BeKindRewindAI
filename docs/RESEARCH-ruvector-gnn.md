# Research: ruvector-gnn — Self-Learning Search Improvement

**Date:** 2026-04-01
**Bead:** 652514db-edc3-452d-8b9d-0a685a04e412
**Agent:** Shadow (polecat)

## Summary

**What the GNN Layer Does:**
The GNN layer (Graph Neural Network) operates directly on the HNSW graph topology. It performs message passing — aggregating neighbor node features to compute improved embeddings. Unlike standard HNSW which treats the graph as a flat lookup, the GNN understands the graph structure and learns which neighbors matter for each query.

**How It Improves Over HNSW:**
- Multi-head Graph Attention (GAT) learns which neighboring vectors are most relevant per query
- GraphSAGE enables inductive learning — can handle new, unseen nodes without retraining
- The GNN re-ranks HNSW neighbors using learned attention weights, so results improve over time as query patterns are observed
- Standard HNSW returns the same results every time; GNN-HNSW adapts to usage patterns

**API — Vector In, Better Vector Out:**
```rust
// Input: raw node features + HNSW adjacency list
let features = Array2::zeros((1000, 128));  // node embeddings
let adjacency: Vec<Vec<usize>> = /* HNSW neighbors */;

// Output: GNN-refined embeddings
let output = gcn.forward(&features, &adjacency)?;

// Integration with Ruvector core:
let gnn_embeddings = gnn.encode(&db.get_all_vectors()?, &hnsw_graph)?;
let results = db.search_with_gnn(&query_vector, &gnn, 10)?;
```

**Accessibility via mcporter/Python:**
- **NOT directly via mcporter** — mcporter is the MCP server for RVF format, not the GNN
- **Node.js (NAPI-RS):** YES — `@ruvector/gnn` npm package available with full TypeScript support
- **WASM:** YES — `ruvector-gnn-wasm` crate provides WebAssembly bindings
- **Python:** NO direct PyO3 binding found for the GNN crate specifically
- The GNN operates as a layer on top of the core HNSW index; it requires integration with `ruvector-core`

**Performance Overhead vs Regular HNSW:**
- GCN forward (1 layer): ~15ms for 100K nodes, avg degree 16
- GAT forward (8 heads): ~45ms
- GraphSAGE (2 layers): ~25ms
- Memory: ~50MB for 1-layer model, ~150MB for 4-layer
- With mmap weights: only ~10MB RAM + disk
- SIMD-optimized aggregation keeps overhead under 15ms for typical workloads
- Regular HNSW search is ~0.1-1ms; GNN adds ~15-45ms but only during indexing/refresh, not per-query

**How the Learning Works:**
- **No training required for inference** — pre-trained weights can be loaded via `save_weights()`/`load_weights()`
- **Inductive learning via GraphSAGE** — can generalize to new nodes without retraining
- **Attention weights learn from query patterns** — during search, the GNN learns which neighbor connections matter
- The model is trained offline on the graph structure, then deployed for inference
- For BeKindRewindAI: vocabulary vectors would need pre-training, then GNN re-ranking during search

## Recommendation for BeKindRewindAI

**ruvector-gnn is NOT recommended for BeKindRewindAI at this time** because:
1. No Python bindings — would require writing a PyO3 wrapper or using Node.js
2. No mcporter integration — cannot access via the existing Python API
3. Training overhead — needs pre-trained model for best results; not truly "self-learning" out of the box
4. Performance overhead (~15-45ms) may be significant for real-time vocabulary search

**Alternative:** The GNN's benefits (learning from query patterns) align with BeKindRewindAI's needs, but the implementation gap is too large. A simpler approach would be to implement query result feedback loops directly in Python using the existing RuVector search API.