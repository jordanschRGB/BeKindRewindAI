# Research: ruvector-postgres + ruvector-collections

## ruvector-postgres

**ruvector-postgres** is a PostgreSQL extension (MIT licensed) that claims to be a drop-in pgvector replacement with 143 SQL functions. Install via Docker (`ruvnet/ruvector-postgres:latest`) or build from source with `cargo pgrx install --release`. After installation, enable with `CREATE EXTENSION ruvector;`.

**Drop-in for pgvector?** Yes, for basic vector operations. It uses the same `ruvector(n)` type, supports HNSW (`USING ruhnsw`) and IVFFlat indexes, and the `<->`, `<=>`, `<#>`, `<+>` distance operators. Existing pgvector tables can migrate by changing the type name.

**Does it add 230+ SQL functions?** The README claims 143 functions across: vector ops, 46 attention mechanisms, hyperbolic geometry (8), sparse vectors + BM25 (14), sublinear solvers (11), spectral/TDA math (19), GNN layers (5), Tiny Dancer routing (11), local embeddings (6), SONA self-learning (4), Neural DAG (59), Cypher/SPARQL (22), gated transformers (13), hybrid search (7), multi-tenancy (17), self-healing (23), and integrity control (4). These are all native PostgreSQL functions callable via SELECT.

**Local embedding generation:** 6 fastembed models run inside PostgreSQL (all-MiniLM-L6-v2, bge-small/base/large-en-v1.5, nomic-embed-text-v1/v1.5). No external API calls needed.

**Self-healing indexes:** Automated integrity checks with Stoer-Wagner mincut validation. Can detect fragmentation, orphaned nodes, and auto-repair.

**Multi-tenancy:** Built-in row-level tenant isolation with `ruvector_set_tenant('tenant_id')` — no extra implementation needed.

## ruvector-collections

**ruvector-collections** is a Rust crate (`ruvector-collections = "0.1.1"`) providing in-memory multi-tenant collection management for RuVector vector databases. It is NOT part of the PostgreSQL extension — it's a separate library.

**What are collections?** Logical namespaces for grouping vectors with isolated schemas. Each collection has: name, dimensions, distance metric (Cosine/L2/Dot), vector type (Float32), metadata (JSON), and optional aliases. A `CollectionManager` handles CRUD operations.

**Multi-tenant?** Yes — collections are isolated namespaces. Each tenant can have its own collection(s) with separate schemas and metadata.

**Schema-managed?** Yes. Schemas are enforced: you define `dimensions`, `distance_metric`, and `vector_type` at collection creation. Inserting vectors with wrong dimensions fails validation.

**Persistence?** In-memory only (DashMap). No persistence layer is mentioned — this is a client-side library, not a database. For persistence, you'd pair it with ruvector-postgres or ruvector-core.

## Should BeKindRewindAI Consider PostgreSQL Instead of Flat Files?

**Arguments for ruvector-postgres:**
- Scalable vector search with HNSW indexes (handles 1M+ vectors vs. flat file in-memory)
- Local embedding generation eliminates OpenAI API calls for vocabulary extraction
- Multi-tenancy built-in (useful if multiple users share the same database)
- Self-healing indexes reduce operational burden
- Free (MIT) vs. per-query cloud costs
- SQL query interface is familiar and integrates with existing PostgreSQL tooling

**Arguments against (stay with flat files):**
- BeKindRewindAI's vocabulary is described as "in memory (flat files)" — this is likely small scale (thousands of terms, not millions)
- Adding PostgreSQL introduces a new service to deploy and maintain
- ruvector-postgres is a new/unproven extension compared to pgvector which is battle-tested
- The "143 functions" and "self-learning" claims are aggressive marketing — practical reliability is unknown
- Flat files are simpler: no connection pooling, no extension installation, no schema migrations

**Recommendation:** For the current scale of "vocabulary in flat files," PostgreSQL is likely overkill. However, if BeKindRewindAI grows to need: (1) multiple concurrent users with isolated vocabularies, (2) vocabulary search across 100K+ terms, or (3) elimination of OpenAI API dependency — then ruvector-postgres is worth evaluating. Start with pgvector (simpler, proven) before ruvector-postgres. ruvector-collections is only relevant if building a multi-collection service layer in Rust.
