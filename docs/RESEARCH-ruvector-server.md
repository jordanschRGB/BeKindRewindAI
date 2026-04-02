# Research: ruvector-server

## What the Full Server Provides Beyond CLI mcporter

**mcporter** is an MCP (Model Context Protocol) server — a CLI tool for AI agents to call RuVector tools via stdio or SSE. It's agent-facing, not user-facing.

**ruvector-server** is a full Axum-based HTTP REST API server. It provides:

| Capability | mcporter (CLI) | ruvector-server |
|---|---|---|
| Protocol | MCP/stdio/SSE | HTTP/REST |
| Vector CRUD | Yes | Yes |
| k-NN search | Yes | Yes |
| Batch operations | No | Yes (batch insert, batch search) |
| Multi-collection management | Partial | Full (create, list, describe, delete) |
| Health/readiness probes | No | Yes (`/health`, `/ready`) |
| CORS support | No | Yes (configurable origins) |
| GZIP compression | No | Yes |
| Request tracing | No | Yes (tower-http) |
| Production deployment | No (local/stdio) | Yes (background server) |
| OpenAPI docs | No | Yes (auto-generated) |

**ruvector-server also uses ruvector-core v0.1.2** under the hood, giving it the same HNSW/graph-vector engine as the CLI.

---

## How to Run on Mac/Windows

### Current Build Status
- docs.rs shows builds only for **x86_64-unknown-linux-gnu** — no official Mac or Windows binaries.
- The Docker path is documented:

```dockerfile
FROM rust:1.77 as builder
WORKDIR /app
RUN cargo build --release -p ruvector-server

FROM debian:bookworm-slim
COPY --from=builder /app/target/release/ruvector-server /usr/local/bin/
EXPOSE 8080
CMD ["ruvector-server"]
```

### Options for Mac/Windows

1. **Docker (works today)**: The Linux binary runs fine in Docker on Mac (`docker run -p 8080:8080 ...`) or Windows (WSL2/Docker Desktop). This is the most reliable path now.

2. **Build from source**: `cargo install ruvector-server` or build from the repo — requires Rust 1.77+. Would work on Mac/Windows natively but no pre-built binaries are published.

3. **npm alternative**: `@ruvector/server` v0.1.0 is published on npm (HTTP/gRPC server with REST API + streaming) but is a different version (0.1.0 vs Rust 0.1.30). Not clear if it's a wrapper or separate implementation.

4. **ruvector-cli**: The CLI v2.0.4 IS cross-platform (Mac/Windows) and has MCP protocol support. But it lacks the REST API, CORS, and production-server features.

**Verdict**: Docker is the practical path for Mac/Windows today. Native binaries would require building from source or someone publishing cross-platform releases.

---

## APIs Exposed

### Endpoints

```
GET  /health                          # Liveness probe
GET  /ready                           # Readiness probe

POST /collections                     # Create collection
GET  /collections                    # List all collections
GET  /collections/{name}             # Get collection info (dimensions, count, distance metric)
DELETE /collections/{name}            # Delete collection

POST /collections/{name}/vectors      # Insert vector(s)
GET  /collections/{name}/vectors/{id} # Get vector by ID
DELETE /collections/{name}/vectors/{id} # Delete vector

POST /collections/{name}/search       # k-NN search
POST /collections/{name}/search/batch # Batch search across multiple queries
```

### Request/Response Shapes

**Create collection**:
```json
{ "name": "docs", "dimensions": 384, "distance_metric": "cosine" }
```

**Upsert vector**:
```json
{ "id": "doc-1", "vector": [0.1, ...], "metadata": { "title": "Hello" } }
```

**Search**:
```json
{ "vector": [0.1, ...], "k": 10, "filter": { "category": "tech" } }
```

**Search response**:
```json
{ "results": [{ "id": "doc-1", "score": 0.95, "metadata": {...} }], "took_ms": 2 }
```

**Error format**:
```json
{ "code": "NOT_FOUND", "message": "Collection 'docs' not found", "details": null }
```

### Configuration (`ServerConfig`)
- `host`, `port` — bind address
- `cors_origins` — allowed origins
- `enable_compression` — GZIP
- `max_body_size` — request size limit
- `request_timeout` — per-request timeout

---

## Could This Enable RuVector on Mac/Windows for BeKindRewindAI?

**Yes — with Docker**, this is the most viable path.

### Architecture Possibility

```
BeKindRewindAI (Node.js)
    |
    +-- HTTP REST --> ruvector-server (Docker on Mac/Windows)
                            |
                            +-- ruvector-core (HNSW, graph search, encoding)
```

### Why This Works
- The REST API is language-agnostic — any HTTP client (fetch, axios, node-fetch) works from Node.js/Python/etc.
- CORS is built-in, so browser clients or cross-origin setups are fine.
- Batch search endpoint supports the multi-vocabulary search pattern BeKindRewindAI uses.
- Docker isolates the Linux binary — no cross-platform Rust compilation needed on the user's machine.

### Gaps & Concerns
- **No Python bindings** — if BeKindRewindAI wanted to call ruvector-core directly from Python, this doesn't help. They'd still need PyO3 bindings or the CLI subprocess approach.
- **Docker dependency** — requires users to have Docker Desktop running. For some users this is a heavy requirement.
- **No authentication** (v0.1.30) — API key auth is "planned". Production deployment would need a reverse proxy (nginx, Traefik) for auth.
- **No gRPC in Rust crate** — `@ruvector/server` npm mentions gRPC, but the Rust crate is HTTP-only. Unclear if they are in sync.
- **Performance overhead** — HTTP/REST vs in-process calls adds latency. For high-throughput labeling pipelines this could matter.

### Comparison to Alternatives for Mac/Windows

| Approach | Works on Mac/Windows? | Ease | Performance | Production-ready? |
|---|---|---|---|---|
| ruvector-server (Docker) | Yes (via Docker) | Medium (Docker required) | Good | Yes (CORS, compression, tracing) |
| ruvector-cli MCP (subprocess) | Yes (native binary) | Easy | Medium (stdio overhead) | No (CLI tool) |
| Build ruvector-server from source | Yes (with Rust) | Hard | Best (native) | Yes |
| ruvlite (lightweight alternative) | Unknown | Unknown | Unknown | Unknown (still researching) |

---

## Key Takeaways

1. **ruvector-server** is a production-grade REST API wrapper around ruvector-core. It adds meaningful infrastructure features (CORS, compression, health checks, batch ops) that mcporter lacks.

2. **Docker is the Mac/Windows path** for now. The Linux binary works in containers; native Mac/Windows binaries are not published.

3. **For BeKindRewindAI**: The HTTP API approach is clean and deployable. A Node.js service could spin up the Docker container on startup or connect to a pre-running ruvector-server container. This avoids the subprocess/stdio overhead of mcporter.

4. **Watch for**: API key auth (not yet implemented), parity between npm `@ruvector/server` and Rust crate versions, and whether pre-built Docker images are published to a registry (GHCR, Docker Hub) vs needing to build from source.
