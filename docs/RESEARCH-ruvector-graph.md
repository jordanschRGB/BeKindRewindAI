# Research: ruvector-graph + ruvector-graph-transformer

**Bead:** `060c357f-c62d-4485-9cf5-09791f017fce`
**Crates:** `ruvector-graph` v2.0.6, `ruvector-graph-transformer` v2.0.4
**Source:** crates.io, docs.rs, GitHub/ruvnet/RuVector ADR docs

---

## 1. How does this graph store and query data differently from a flat vector index?

A flat HNSW vector index (like ruvector-core) stores vectors in a hierarchical navigable small-world graph — purely similarity-based, no relationships, no properties. You query by approximate K-nearest neighbors (ANN) in vector space.

**ruvector-graph** layers a property graph on top of ruvector-core's vector engine:

- **Property graph**: nodes and edges have typed IDs, string labels, and arbitrary key-value `Properties` (JSON-like values). Edges are directed binary relationships; hyperedges support N-ary relations.
- **Neo4j-compatible Cypher parser**: full lexing/parsing/semantic analysis + query optimizer, with hyperedge support added on top of standard Cypher.
- **Hybrid query system** (`hybrid/` module): combines vector similarity with graph pattern matching. `VectorCypherParser` extends Cypher with similarity predicates; `SemanticSearch` blends graph traversal with ANN scoring. `HybridIndex` indexes graph elements (nodes, edges, hyperedges) as vectors via ruvector-core, enabling ANN search within graph substructures.
- **GNN inference**: `GraphNeuralEngine` + `GraphEmbedding` run graph neural network message-passing over the stored graph structure, producing learned node/edge embeddings that capture topology — not just raw vector geometry.
- **Distributed**: optional Raft consensus, gossip membership, sharding, replication for multi-node deployments.

Query model comparison:

| | Flat HNSW (ruvector-core) | ruvector-graph |
|---|---|---|
| Index structure | Single vector HNSW | Property graph + embedded HNSW + GNN |
| Query types | ANN by vector similarity | ANN + Cypher patterns + GNN embeddings + graph traversal |
| Relationships | None | First-class edges/hyperedges with types/properties |
| ACID | No | Yes (MVCC transactions) |
| Distribution | No | Yes (raft/replication/sharding) |

---

## 2. What are the edge types and how are they weighted?

**Binary edges** (`Edge` struct): `id`, `from NodeId`, `to NodeId`, `edge_type: String`, `properties: Properties`

- `edge_type` is a freeform string label (e.g., `"appears_with"`, `"located_at"`, `"temporal_next"`). No built-in enumerated type list — any string works.
- **Properties** on edges carry arbitrary metadata: key-value pairs where values are `PropertyValue` enum (String, I64, F64, Bool, Vec, JSON).
- **Weights are implicit** via properties — there is no built-in numeric `weight` field. If you want a weight, you set a property like `{"weight": 0.85}`. The graph does not enforce or normalize these.
- Edge queries are by type (`get_edges_by_type`), source/destination (`get_outgoing_edges`, `get_incoming_edges`), or full property filters (`get_nodes_by_property`).

**Hyperedges** (`Hyperedge` struct): N-ary relations connecting multiple nodes. Built with `HyperedgeBuilder`. `get_hyperedges_by_node` retrieves all hyperedges containing a node.

No built-in temporal versioning on edges — the `temporal` feature flag in graph-transformer handles time via separate snapshot/evolving mechanisms.

---

## 3. Could this model VHS memories — episodes, characters, locations connected over time?

**Yes, quite naturally.** Here's how:

**Nodes:**
- `Episode` nodes: label `"episode"`, properties `{title, date, duration, transcript_summary}`
- `Character` nodes: label `"character"`, properties `{name, description, embedding: Vec<f32>}`
- `Location` nodes: label `"location"`, properties `{name, description}`
- `Scene` nodes: label `"scene"` (granular within episode), properties `{start_time, end_time}`

**Binary edges:**
- `(Episode)-[:has_character]->(Character)` — character appears in episode
- `(Episode)-[:set_in]->(Location)` — episode location
- `(Scene)-[:part_of]->(Episode)` — scene belongs to episode
- `(Scene)-[:follows]->(Scene)` — temporal sequence within episode
- `(Character)-[:interacts_with {weight: 0.85}]->(Character)` — character interaction strength

**Hyperedges:**
- `(Character A, Character B, Episode E, Scene S)` via hyperedge type `"co_occurrence"` — models who was together where/when
- `(Location, Episode, TimeRange)` hyperedge for episode setting

**Graph traversal queries:**
```cypher
MATCH (c:Character {name: "Alice"})-[:has_character]->(e:Episode)
      -[:set_in]->(l:Location)
RETURN e, l
```
Find all episodes featuring Alice and their locations.

**GNN embeddings:** The `GraphNeuralEngine` runs message-passing over this structure, producing per-node embeddings that encode:
- Which characters tend to co-appear (learned via graph conv)
- Which locations cluster together across episodes
- Temporal flow through scenes/episodes

**Temporal module** (graph-transformer `temporal` feature): provides causal masking and Granger causality extraction — could identify which memories cause others (e.g., character behavior in episode N influences episode N+3).

**Limitation:** There is no built-in "versioning" or "timestamp ordering" — you manage temporal relationships explicitly via edges (`[:follows]`) and properties (`{date: "2024-01-15"}`). No automatic time-ordered traversal.

---

## 4. What are the query APIs — range queries, path queries, subgraph extraction?

**GraphDB API** (synchronous in-memory):
- `create_node`, `get_node`, `delete_node`, `get_nodes_by_label`, `get_nodes_by_property`
- `create_edge`, `get_edge`, `delete_edge`, `get_edges_by_type`, `get_outgoing_edges`, `get_incoming_edges`
- `create_hyperedge`, `get_hyperedge`, `get_hyperedges_by_node`
- `node_count`, `edge_count`, `hyperedge_count`

**Cypher query engine** (full parser + optimizer):
- `parse_cypher()` → AST → semantic analysis → optimization plan → execution
- Supports MATCH, WHERE, RETURN, WITH, ORDER BY, LIMIT, UNION
- **Extended with similarity predicates** via `VectorCypherParser` — vector ANN filters inside Cypher patterns
- `QueryOptimizer` with cost-based planning

**Hybrid vector-graph queries:**
- `HybridQuery`: combines graph pattern + vector similarity constraint
- `VectorConstraint`: ANN radius/knn filter applied at graph traversal boundary
- `SemanticSearch`: traverses graph and re-ranks by vector similarity

**GNN APIs:**
- `GraphNeuralEngine::forward()` — run GNN forward pass
- `GraphEmbedding` — get per-node learned embeddings
- `LinkPrediction` — predict likely edges
- `NodeClassification` — assign labels to nodes based on topology

**Path queries** via Cypher:
```cypher
MATCH path = (a:Character)-[:interacts_with*1..3]->(b:Character)
WHERE a.name = "Alice" AND b.name = "Bob"
RETURN path
```
Supports variable-length path traversal with Cypher's `*min..max` notation.

**Subgraph extraction:** Not a single API call — achieved by:
1. Cypher `MATCH` with a pattern to collect matching nodes/edges
2. Iterate `get_outgoing_edges` / `get_incoming_edges` from a seed node up to N hops
3. Or use the GNN to compute embeddings then use vector similarity on the resulting subgraph embeddings

**Distributed APIs** (with `distributed` feature):
- `GraphShard`, `ShardCoordinator`, `ShardStrategy` — horizontal sharding
- `Federation` — cross-cluster federation
- `RpcServer`/`RpcClient` — gRPC-based distributed query execution
- `GraphReplication` — replica coordination

---

## 5. How would Python call this — WASM, server, or CLI?

**ruvector-graph (v2.0.6):**

| Access method | Available | Details |
|---|---|---|
| **WASM** | No direct binding | Only through ruvector-graph-transformer-wasm (see below) |
| **CLI** | No | No CLI binary published to crates.io |
| **Rust server (Axum)** | Yes | `hyper`, `tonic` (gRPC) features — you build and host a Rust server |
| **Node.js npm** | No | Only ruvector (core) has npm bindings, not this specific crate |
| **Direct from Python** | No | No PyO3 bindings. Could call a hosted Rust server over HTTP/gRPC |

**ruvector-graph-transformer (v2.0.4):**

| Access method | Available | Details |
|---|---|---|
| **WASM** | Yes | `ruvector-graph-transformer-wasm` — wasm-pack build, runs in browser |
| **Node.js (NAPI-RS)** | Yes | `@ruvector/graph-transformer` npm package — native Node.js addon |
| **CLI** | No | No CLI binary published |
| **Python** | Indirect | Call the Node.js package via ` subprocess` or use the WASM in a JS environment |

**Summary for BeKindRewindAI Python integration:**

- **Best path**: Run a **ruvector-server** (Axum HTTP) that wraps ruvector-graph. Your Python code calls it over REST — same integration pattern as ruvector-core. This is the practical path.
- **Alternative**: If you want GNN inference or graph-transformer features from Python, wrap the **Node.js `@ruvector/graph-transformer`** npm package using `subprocess` or a Python Node.js FFI wrapper.
- **WASM**: `ruvector-graph-transformer-wasm` exists, but browser-based usage only — not useful for a Node.js/python server context.
- **No native Python bindings** for either crate. No PyO3. No GRPC Python codegen out of the box.

---

## Verdict: Replace or enhance flat HNSW for BeKindRewindAI?

**Replace? No.** Flat HNSW (ruvector-core) is still needed for raw vocabulary/transcript ANN search — the Dreamer agent's Whisper vocabulary lookups need pure similarity, not graph structure.

**Enhance? Yes.** Use ruvector-graph as a **memory graph layer** on top of flat HNSW:
1. ruvector-core HNSW for fast vocabulary/embedding lookup (what it already does)
2. ruvector-graph for the **episodic memory graph** — episodes, characters, locations, scene graph with hyperedges
3. GNN inference over the memory graph for **learned recall** — instead of just ANN on flat vectors, traverse the graph to find conceptually related memories via topology
4. ruvector-graph-transformer for **temporal-causal reasoning** — understand which memory events cause later ones

**Key practical blocker**: Neither crate has native Python bindings. You'd need to either run a Rust server (extra infrastructure) or shell out to the Node.js package. This significantly raises the integration cost for BeKindRewindAI's current architecture.
