# Research: ruvector-gnn (Graph Neural Networks)

## 1. GNN Architectures Implemented

**ruvector-gnn** implements three distinct GNN approaches:

### GAT (Graph Attention Network)
- **Location**: `src/graphmae.rs` (`GATEncoder`, `GATLayer`)
- Multi-head self-attention with leaky ReLU activation
- Each head computes: `attention_score = leaky_relu(attn_src · proj_query + attn_dst · proj_key)`
- Attention weights normalized via softmax over neighbors
- Residual connections with layer normalization
- Default config: 4 heads, 2 layers, 64-dim hidden

### GraphSAGE-style Aggregation
- **Location**: `src/layer.rs` (`RuvectorLayer::aggregate_messages`)
- Weighted mean aggregation of neighbor messages
- Edge weights normalize neighbor contributions: `w_i = w_i / Σw`
- Used alongside attention in the hybrid `RuvectorLayer`

### GraphMAE (Masked Autoencoder for Graphs)
- **Location**: `src/graphmae.rs`
- Self-supervised pre-training: mask node features → GAT encode → re-mask latent → decode masked only → SCE/MSE loss
- **Pipeline**: `mask → GAT Encode → re-mask → decode masked only → SCE loss`
- Reference: Hou et al., "GraphMAE: Self-Supervised Masked Graph Autoencoders", KDD 2022
- Supports degree-centrality masking (higher-degree nodes masked more often)
- Loss functions: Scaled Cosine Error `(1 - cos_sim)^γ` or MSE

### Custom Hybrid: RuvectorLayer
- **Location**: `src/layer.rs`
- Combines GAT attention + GraphSAGE aggregation + GRU recurrent update
- Forward pass: message transform → attention aggregation → weighted aggregation → combine → GRU update → dropout → layer norm
- Designed to operate on **HNSW graph topology** specifically

### Continual Learning Support
- Elastic Weight Consolidation (EWC): prevents catastrophic forgetting
- Experience Replay Buffer: reservoir sampling for uniform coverage
- Learning rate schedulers: cosine annealing, warmup, ReduceOnPlateau

---

## 2. Relation to graph-transformer Crate

`ruvector-graph-transformer` (`src/`) is the **upper orchestration layer** that composes multiple RuVector crates:

| Aspect | ruvector-gnn | ruvector-graph-transformer |
|--------|---------------|---------------------------|
| Role | Foundational GNN layers | Unified interface with proof-gated mutation |
| GNN Types | GAT, GraphSAGE, GraphMAE | Delegates to ruvector-gnn + adds physics/biological/manifold attention |
| Verification | None | Proof-gated mutations, verified training with certificates |
| Features | Training utilities, compression, mmap | Sublinear attention, temporal causality, economic game theory |
| Entry Point | `RuvectorLayer`, `GraphMAE` | `GraphTransformer` |

**Relationship**: `ruvector-graph-transformer` is a facade/composer that could use `ruvector-gnn` as its GNN backbone while adding:
- Sublinear O(n log n) attention via LSH and PPR sampling
- Physics: Hamiltonian graph networks with energy conservation
- Biological: spiking attention with STDP/Hebbian learning
- Manifold: product manifold attention (S^n × H^m × R^k)
- Temporal: causal temporal attention with Granger causality
- Verified training with per-step proof certificates

---

## 3. Input/Output Interfaces

### Primary Data Structures

```rust
// Graph input format (src/graphmae.rs)
struct GraphData {
    node_features: Vec<Vec<f32>>,  // [node_id] → feature vector
    adjacency: Vec<Vec<usize>>,      // [node_id] → neighbor indices
    num_nodes: usize,
}

// GNN layer forward (src/layer.rs)
RuvectorLayer::forward(
    node_embedding: &[f32],           // current node's embedding
    neighbor_embeddings: &[Vec<f32>], // embeddings of neighbors
    edge_weights: &[f32],             // edge weights (e.g., distances)
) → Vec<f32>                          // updated embedding

// Query interface (src/query.rs)
struct RuvectorQuery {
    vector: Option<Vec<f32>>,
    text: Option<String>,
    node_id: Option<u64>,
    mode: QueryMode,        // VectorSearch | NeuralSearch | SubgraphExtraction | DifferentiableSearch
    k: usize,
    ef: usize,              // HNSW exploration factor
    gnn_depth: usize,
    temperature: f32,
    return_attention: bool,
}

struct QueryResult {
    nodes: Vec<u64>,
    scores: Vec<f32>,
    embeddings: Option<Vec<Vec<f32>>>,    // GNN-processed embeddings
    attention_weights: Option<Vec<Vec<f32>>>,
    subgraph: Option<SubGraph>,
    latency_ms: u64,
}
```

### Key API Entry Points

| Function | Purpose |
|----------|---------|
| `GraphMAE::train_step(&self, graph: &GraphData) → f32` | Self-supervised training step |
| `GraphMAE::encode(&self, graph: &GraphData) → Vec<Vec<f32>>` | Inference: get all node embeddings |
| `RuvectorLayer::forward(node, neighbors, weights)` | Single GNN layer pass |
| `differentiable_search(query, candidates, k, temp)` | Soft attention search with temperature |
| `hierarchical_forward(query, layer_embeddings, gnn_layers)` | Multi-layer GNN traversal |
| `info_nce_loss(anchor, positives, negatives, temp)` | Contrastive loss for embedding learning |
| `local_contrastive_loss(node, neighbors, non_neighbors, temp)` | Graph-structure-aware contrastive loss |

---

## 4. VHS Tape Memory Use Cases

### Could This Model VHS Tape Relationships?

**Yes, with caveats.** Here's how each architecture maps to BeKindRewindAI's memory graph:

#### Node Representation (Tapes/Segments)
- Each VHS tape or transcript segment becomes a node
- Node features = embedding from `ruvector-cnn` (512-dim MobileNet-V3) + transcript embedding + metadata
- Temporal features: tape capture date, position in tape sequence

#### Edge Types (Relationships)
- **Semantic similarity**: Cosine similarity between transcript embeddings → edge weights
- **Temporal proximity**: Recordings within same tape or same day → graph edges
- **Shared vocabulary**: Terms appearing in multiple transcripts → topical edges

#### Finding Semantic Clusters
```rust
// Example workflow:
// 1. Build GraphData from tape metadata
let graph = GraphData {
    node_features: tape_embeddings,  // CNN + transcript embeddings
    adjacency: semantic_neighbors,    // k-NN based on cosine similarity
    num_nodes: num_tapes,
};

// 2. Self-supervised pre-training (no labels needed!)
let model = GraphMAE::new(GraphMAEConfig {
    mask_ratio: 0.5,
    hidden_dim: 128,
    num_heads: 4,
    num_layers: 2,
    ..Default::default()
});
// train_step() learns tape representations without any labels

// 3. Get embeddings for clustering
let embeddings = model.encode(&graph);
// Run k-means or UMAP on embeddings for semantic clusters
```

#### Inferring Hidden Connections
- `local_contrastive_loss` encourages a tape's embedding to be similar to its neighbors and dissimilar to non-neighbors
- This can **infer implicit relationships**: if tape A is similar to tape B, and tape B is similar to tape C, the GNN propagates that signal to suggest A→C connection
- `hierarchical_forward` allows multi-hop reasoning: query traverses 2-3 GNN layers to find distant but related recordings

#### Grader/Dreamer Integration Points
- **Grader** (quality assessment): GNN embeddings could provide context for quality scoring — low-quality tapes may cluster separately
- **Dreamer** (hallucination detection): Graph structure reveals unexpected connections — if a "memory" connects tapes that share no vocabulary, it's suspicious

---

## 5. Python Access: WASM, Server Binary, or Something Else?

### Summary: **NOT Python-Native**

| Binding Type | Available? | Crate |
|-------------|-----------|-------|
| PyO3 | **NO** | Not built |
| WASM | **NO** (for ruvector-gnn directly) | But see `ruvector-graph-transformer-wasm` |
| NAPI-RS (Node.js) | **NO** (for ruvector-gnn directly) | But see `ruvector-graph-node` |
| gRPC/REST server | **Maybe** | `ruvector-graph` may provide this |

### Actual Access Patterns

1. **`ruvector-gnn` is pure Rust** — no Python bindings, no WASM, no NAPI-RS. To use it, you must integrate as a Rust dependency.

2. **Related crates that ARE accessible from Python:**
   - `ruvector-graph-wasm`: WASM-compiled graph operations
   - `ruvector-graph-transformer-wasm`: Same, for the transformer composition
   - These provide graph-level operations, not the raw GNN layer API

3. **If you need Python access to GNN functionality**, options are:
   - **PyTorch Geometric**: Use PyG's GATConv, SAGEConv implementations instead (battle-tested, Python-native)
   - **Custom Rust server**: Wrap `ruvector-gnn` in a Rust binary with gRPC or REST, call from Python
   - **WASM via `ruvector-graph-transformer-wasm`**: If the higher-level API is sufficient

### Performance Characteristics
- Per the code, GNN forward pass overhead is **15-45ms** vs 0.1-1ms for regular HNSW — significant latency for real-time queries
- Compression module (`src/compress.rs`) provides multi-level quantization (FP16, PQ8, PQ4, binary) to reduce memory/compute

---

## Verdict for BeKindRewindAI

**Low immediate relevance** due to lack of Python bindings and high per-query overhead. However, the **conceptual value is high**:

1. **GraphMAE** is ideal for learning tape representations without labels — great for cold-start
2. **Contrastive loss** (`info_nce_loss`) could learn "this tape is like that one" from co-occurrence
3. **If BeKindRewindAI moves to a Rust-native pipeline** (or adds a gRPC wrapper), `ruvector-gnn` could provide sophisticated memory graph analytics
4. **For Python-native GNN**, use PyTorch Geometric instead — same GAT/GraphSAGE architectures, full Python integration

**Recommendation**: Document as "future Rust integration target" but implement semantic clustering in Python using scikit-learn on CNN embeddings for now.
