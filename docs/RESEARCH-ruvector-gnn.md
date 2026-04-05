# Research: ruvector-gnn

## Summary

The `ruvector-gnn` crate is a Graph Neural Network layer that operates on HNSW (Hierarchical Navigable Small World) vector index topology. It adds learned, adaptive re-ranking to otherwise-static vector search.

## 1. GNN Architectures Implemented

**ruvector-gnn implements three core GNN architectures:**

| Architecture | Description |
|-------------|-------------|
| **GCN** (Graph Convolutional Network) | Standard graph convolution forward pass over HNSW neighbors. Learns structural patterns without manual feature engineering. |
| **GAT** (Graph Attention Network) | Multi-head Graph Attention with interpretable attention weights. Each head learns different attention patterns, allowing the model to discover which neighbors are most relevant per query. |
| **GraphSAGE** | Inductive learning with neighbor sampling. Handles new, unseen nodes without retraining the full model. Supports Mean, Max, and LSTM aggregators. |

**Additional capabilities:**
- SIMD-optimized aggregation (target: <15ms for 100K-node graphs)
- Memory-mapped weight storage for models larger than RAM
- INT8/FP16 quantization (2-4x compression)
- Skip connections (residual connections for deep stacks)
- Layer normalization
- Batch processing via Rayon parallelism

**Training features:**
- Adam optimizer with momentum and bias correction
- Experience replay buffer with reservoir sampling
- EWC (Elastic Weight Consolidation) for continual learning
- Learning rate schedulers (CosineAnnealing, warmup, plateau detection)
- GraphMAE (Masked Autoencoder for Graphs) pre-training

## 2. Relationship to graph-transformer Crate

**ruvector-graph-transformer** depends on `ruvector-gnn` and extends it with:

```
ruvector-graph-transformer
├── ruvector-gnn         ← base GNN message passing
├── ruvector-attention   ← scaled dot-product attention
├── ruvector-mincut      ← graph structure operations
├── ruvector-verified    ← formal proofs, attestations
├── ruvector-solver      ← sparse linear systems
└── ruvector-coherence   ← coherence measurement
```

**Key additions in graph-transformer:**
- **Proof-gated mutation**: Every graph state change requires formal proof of validity
- **Sublinear attention**: O(n log n) attention via LSH/PPR/spectral methods (vs O(n²) standard)
- **8 specialized modules**: physics, biological, manifold, temporal-causal, economic, self-organizing, verified-training, sublinear-attention
- **Manifold geometry**: Product manifolds S^n × H^m × R^k instead of just Euclidean
- **Verified training**: Training certificates, delta-apply rollback, fail-closed on invariant violations

**Relationship**: `ruvector-gnn` is the foundational GNN layer. `ruvector-graph-transformer` is a higher-level wrapper that adds formal verification, multiple attention mechanisms, and domain-specific modules. The GNN provides the core message-passing; the transformer adds proof safety and specialized architectures.

## 3. Input/Output Interfaces

**Input:**
```rust
// Node features: Array2<f32> of shape (num_nodes × input_dim)
// Adjacency: Vec<Vec<usize>> — HNSW neighbors per node

let config = GNNConfig {
    input_dim: 128,
    output_dim: 64,
    hidden_dim: 128,
    num_heads: 4,        // For GAT
    dropout: 0.1,
    activation: Activation::ReLU,
};

// GCN forward
let output: Array2<f32> = gcn.forward(&features, &adjacency)?;

// GAT forward with attention weights
let (output, attention_weights): (Array2<f32>, Vec<Vec<f32>>) = 
    gat.forward_with_attention(&features, &adjacency)?;

// GraphSAGE mini-batch
let embeddings = sage.forward_minibatch(&features, &adjacency, &batch_nodes)?;
```

**Output:**
- `Array2<f32>` of shape `(num_nodes × output_dim)` — learned embeddings
- Optional attention weights for interpretability
- Training loss values (InfoNCE, local contrastive, etc.)

**Integration with Ruvector core:**
```rust
use ruvector_core::VectorDB;
use ruvector_gnn::{HNSWMessagePassing, GNNEmbedder};

let db = VectorDB::open("vectors.db")?;
let gnn = GNNEmbedder::new(config)?;
let hnsw_graph = db.get_hnsw_graph()?;
let gnn_embeddings = gnn.encode(&db.get_all_vectors()?, &hnsw_graph)?;
let results = db.search_with_gnn(&query_vector, &gnn, 10)?;
```

## 4. VHS Tape Memory Graph Applications

**Yes, this could model VHS tape memory relationships.** Here's how:

### Semantic Clustering
- Each VHS tape → node with metadata embeddings (title keywords, date, content description)
- Edges derived from HNSW topology (similar tapes become neighbors in graph)
- GAT attention weights reveal which tape relationships matter most
- Clusters emerge via message passing: tapes that consistently co-activate in attention form semantic groups

### Inferring Connections
- GraphSAGE's inductive learning can generalize to new tapes without retraining
- If "Home Movies 1992" and "Birthday 1993" are both connected to "Family Reunion 1992", the model learns this pattern and could suggest connections for a new "Thanksgiving 1993" tape
- Attention weights are interpretable: "This tape connects to others because of temporal proximity AND shared location keywords"

### Temporal Ordering
- The `ruvector-graph-transformer` crate has temporal-causal modules (ADR-053) for "Causal masking, retrocausal attention, continuous-time ODE, Granger causality"
- Could model how memories trigger each other over time

### Practical Architecture for VHS Memory Graph:
```
Tape Node Features:
- Embeddings from: title, description, transcript, date, location tags
- Dimensionality: 128-256

Graph Edges:
- HNSW similarity (content proximity)
- Temporal edges (same year, adjacent dates)
- Manual links (user-specified "related tapes")

GNN Layer Stack:
1. GCN: learns structural patterns in tape relationships
2. GAT: re-ranks search results using learned attention
3. GraphSAGE: handles new tapes via neighbor sampling

Latency target: ~15-45ms for 1000 tapes with 16 avg connections
```

## 5. Python Access Methods

**Three options, in order of ease-of-use:**

| Method | Package | How |
|--------|---------|-----|
| **Node.js bindings** | `@ruvector/gnn` (npm) | `npm i @ruvector/gnn` — NAPI-RS bindings |
| **WASM** | `ruvector-gnn-wasm` | `wasm-pack build` — works in browser or Node/WasmEdge |
| **CLI subprocess** | `ruvector-cli` | Spawns binary, communicates via JSON |
| **Direct Rust** | `ruvector-gnn` | `Cargo.toml` dependency, native Rust only |

**For Python specifically:**
- **No native Python (PyO3) bindings** exist in the crate
- Python access requires:
  1. **HTTP/gRPC server binary** — wrap GNN in a REST API, Python calls HTTP
  2. **WASM via Pyodide** — run in browser context
  3. **Subprocess + JSON** — spawn `ruvector-cli` binary
  4. **ffi** — manually wrap via cbindgen → C → Python ctypes

**Most practical approach for BeKindRewindAI:**
```python
# Option A: HTTP server (recommended for production)
import requests
# Start: ruvector-gnn-server --port 8080
response = requests.post("http://localhost:8080/gnn/encode", json={
    "vectors": [...],
    "adjacency": [...]
})
embeddings = response.json()["embeddings"]

# Option B: CLI subprocess
import subprocess
result = subprocess.run(
    ["ruvector", "gnn", "encode", "--input", "data.json"],
    capture_output=True, text=True
)
```

## Performance Characteristics

| Operation | Latency (p50) | Notes |
|-----------|---------------|-------|
| GCN forward (1 layer) | ~15ms | 100K nodes, avg degree 16 |
| GAT forward (8 heads) | ~45ms | With attention extraction |
| GraphSAGE (2 layers) | ~25ms | With neighbor sampling |
| Message aggregation | ~5ms | SIMD-accelerated |

Memory: ~50MB for 128→64dim single layer, up to ~150MB for 4 layers. With mmap: ~10MB + disk.

## Key Takeaways for BeKindRewindAI

1. **GNN architectures are GCN, GAT, and GraphSAGE** — proven, mainstream GNN types
2. **graph-transformer builds on this** with formal verification and specialized modules (temporal-causal particularly relevant)
3. **Input: node features + adjacency list** → Output: learned embeddings + optional attention weights
4. **Yes, well-suited for VHS memory graphs** — semantic clustering via GAT attention, temporal ordering via graph-transformer's temporal module
5. **Python access is indirect** — no PyO3, requires HTTP server, WASM, or subprocess wrapper
