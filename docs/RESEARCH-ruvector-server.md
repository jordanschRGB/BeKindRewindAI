# Research: ruvector-server and ruvector-cli (mcporter)

**⚠️ IMPORTANT CORRECTION FIRST:** The `mcporter` CLI mentioned in the bead title is **NOT a RuVector tool**. `mcporter` (by steipete, 3.6k GitHub stars) is a **general-purpose MCP client** — it calls any MCP (Model Context Protocol) server. It is NOT specific to RuVector. The RuVector CLI tool is called **`ruvector-cli`**. This document covers both, but they are different things.

---

## What These Are

### ruvector-server (NOT mcporter)
- **Crate:** `ruvector-server` on crates.io (v0.1.30)
- **What it is:** High-performance REST API server for RuVector, built on **Axum** (Rust HTTP framework) + Tokio async runtime
- **npm equivalent:** `@ruvector/server` (v0.1.0) — same REST API wrapped for Node.js
- **Purpose:** Exposes RuVector functionality via HTTP REST endpoints with CORS, compression, and OpenAPI docs

### ruvector-cli (NOT mcporter)
- **Crate:** `ruvector-cli` on crates.io (v2.0.4)
- **What it is:** Command-line interface + embedded MCP server for RuVector
- **Purpose:** Local database management, vector operations, and MCP protocol server for AI agent integration
- **Note:** Also available as `npm i ruvector` (Node.js package) or `npx ruvector` for quick use

### mcporter (separate project)
- **GitHub:** steipete/mcporter (3.6k stars)
- **What it is:** General-purpose MCP client — can call **any** MCP server (Linear, Context7, Vercel, etc.)
- **NOT RuVector-specific** — it's a universal MCP tool caller
- **Python access to MCP:** Via `subprocess.run(["npx", "mcporter", "call", ...])` or the Node.js API `callOnce()`

---

## ruvector-cli Commands

The `ruvector` CLI exposes these commands:

| Command | Description |
|---------|-------------|
| `ruvector create` | Create a new vector DB with specified dimensions |
| `ruvector insert` | Bulk insert vectors from JSON/CSV/NumPy files |
| `ruvector search` | k-NN search with query vector |
| `ruvector info` | Show database statistics and HNSW config |
| `ruvector benchmark` | Run performance benchmark with random queries |
| `ruvector export` | Export DB to JSON or CSV |
| `ruvector import` | Import from FAISS, Pinecone, Weaviate (planned) |
| `ruvector-mcp` | Start MCP server (stdio or SSE transport) |

Global flags: `-c/--config`, `-d/--debug`, `--no-color`, `-h/help`, `-V/version`

### ruvector-mcp Server Modes

```bash
# STDIO transport (for local AI tools like Claude Desktop)
ruvector-mcp --transport stdio

# SSE transport (for web-based AI tools)
ruvector-mcp --transport sse --host 0.0.0.0 --port 3000
```

**Claude Desktop integration example:**
```json
{
  "mcpServers": {
    "ruvector": {
      "command": "ruvector-mcp",
      "args": ["--transport", "stdio"],
      "env": {
        "RUVECTOR_STORAGE_PATH": "/path/to/vectors.db"
      }
    }
  }
}
```

---

## How Python Would Call These

### Option 1: HTTP REST API (ruvector-server) — RECOMMENDED
Python calls `ruvector-server` over HTTP. **No subprocess needed** — pure HTTP client:

```python
import requests

BASE_URL = "http://localhost:8080"

# Create collection
requests.post(f"{BASE_URL}/collections", json={
    "name": "documents",
    "dimensions": 384,
    "distance_metric": "cosine"
})

# Insert vector
requests.post(f"{BASE_URL}/collections/documents/vectors", json={
    "id": "doc-1",
    "vector": [0.1, 0.2, 0.3],
    "metadata": {"title": "Hello World"}
})

# Search
requests.post(f"{BASE_URL}/collections/documents/search", json={
    "vector": [0.1, 0.2, 0.3],
    "k": 10,
    "filter": {"category": "tech"}
})
```

**No Python client library exists** (as of this research), but the REST API is simple enough to use with `requests` or `httpx`.

### Option 2: subprocess + ruvector CLI
```python
import subprocess
import json

# Search via CLI
result = subprocess.run(
    ["ruvector", "search", "--db", "./vectors.db", "--query", "[0.1,0.2,0.3]", "-k", "10"],
    capture_output=True,
    text=True
)
print(result.stdout)
```

### Option 3: mcporter (NOT RuVector-specific)
If using `mcporter` to call an MCP server that wraps RuVector:
```python
import subprocess
import json

result = subprocess.run(
    ["npx", "mcporter", "call", "ruvector.search", "query:[0.1,0.2,0.3]", "k:10"],
    capture_output=True,
    text=True
)
```

### Option 4: Node.js API for mcporter
```javascript
import { callOnce } from "mcporter";

const result = await callOnce({
    server: "ruvector",  // MCP server name from config
    toolName: "search",
    args: { query: [0.1, 0.2, 0.3], k: 10 },
});
```

---

## ruvector-server REST API Endpoints

Based on the Axum server in `ruvector-server`:

### Health
- `GET /health` — Liveness/readiness probe

### Collections
- `POST /collections` — Create collection
  ```json
  { "name": "docs", "dimensions": 384, "distance_metric": "cosine" }
  ```
- `GET /collections` — List all collections
- `GET /collections/{name}` — Get collection info
- `DELETE /collections/{name}` — Delete collection

### Vectors
- `POST /collections/{name}/vectors` — Insert vector(s)
  ```json
  { "id": "doc-1", "vector": [0.1, 0.2], "metadata": {"title": "..."} }
  ```
- `GET /collections/{name}/vectors/{id}` — Get vector by ID
- `DELETE /collections/{name}/vectors/{id}` — Delete vector

### Search
- `POST /collections/{name}/search` — k-NN search
  ```json
  { "vector": [0.1, 0.2], "k": 10, "filter": {"category": "tech"} }
  ```
- `POST /collections/{name}/search/batch` — Batch search

### Response Shapes
```rust
SearchResponse { results: Vec<SearchResult>, took_ms: u64 }
SearchResult { id: String, score: f32, vector: Option<Vec<f32>>, metadata: Option<serde_json::Value> }
CollectionInfo { name: String, dimensions: usize, count: usize, distance_metric: String }
ApiError { code: String, message: String, details: Option<serde_json::Value> }
```

### Server Config
```rust
ServerConfig {
    host: String,          // default "0.0.0.0"
    port: u16,            // default 8080
    cors_origins: Vec<String>,
    enable_compression: bool,
    max_body_size: usize,
    request_timeout: Duration,
}
```

---

## Root Requirements: Can It Run Without `/opt/ruvector/`?

**YES — it can run without root or `/opt/ruvector/` entirely.**

- **`ruvector-server`**: Is a standalone binary. Run as any user:
  ```bash
  ./ruvector-server  # listens on 0.0.0.0:8080
  # or with custom config
  RUST_LOG=info ./ruvector-server --host 127.0.0.1 --port 3000
  ```
  No installation to `/opt/` required. Just download or `cargo install` the binary.

- **`ruvector-cli`**: No special paths required. Uses:
  - `./ruvector.db` (current dir) by default
  - `~/.config/ruvector/config.toml` for user config
  - `/etc/ruvector/config.toml` for system config (optional)
  - All configurable via `ruvector.toml` or env vars (`RUVECTOR_STORAGE_PATH`)

- **`ruvector-mcp`** (MCP server): Same — no root needed. Just needs a writable database file path.

- **Docker deployment** (if using the published Docker image):
  ```bash
  docker run -p 8080:8080 \
    -v ./data:/data \
    ruvector-server
  ```
  The image uses `debian:bookworm-slim` and runs as non-root by default.

### What about `/opt/ruvector/`?
This path may appear in:
- Default installation paths if using an installer script
- Claude Desktop config examples that show absolute paths
- System-level MCP configuration

But it is **NOT required**. You can store the DB anywhere:
```bash
ruvector create --dimensions 384 --path ~/my-vectors.db
RUVECTOR_STORAGE_PATH=~/my-vectors.db ruvector-mcp --transport stdio
```

---

## Installation Methods

### ruvector-server
```bash
# From crates.io
cargo install ruvector-server

# Docker
docker build -t ruvector-server .
docker run -p 8080:8080 ruvector-server

# Node.js HTTP wrapper
npm install @ruvector/server
```

### ruvector-cli
```bash
# From crates.io
cargo install ruvector-cli

# From npm (Node.js)
npm install ruvector
npx ruvector  # run without installing

# Build from source
git clone https://github.com/ruvnet/ruvector.git
cargo build --release -p ruvector-cli
```

### mcporter (NOT RuVector-specific)
```bash
# npm
npm install mcporter
npx mcporter list

# Homebrew
brew tap steipete/tap
brew install steipete/tap/mcporter
```

---

## Summary Table

| Question | Answer |
|----------|--------|
| **What is mcporter?** | General-purpose MCP client by steipete — calls any MCP server, NOT RuVector-specific |
| **What is ruvector-cli?** | RuVector's own CLI + MCP server (`ruvector-mcp`) |
| **ruvector-cli commands?** | create, insert, search, info, benchmark, export, import, mcp |
| **How does Python call it?** | HTTP REST API (ruvector-server) via `requests`/`httpx` — no subprocess needed |
| **Python subprocess option?** | Yes: `subprocess.run(["ruvector", "search", ...])` for CLI mode |
| **API endpoints?** | POST/GET/DELETE on `/collections`, `/collections/{name}/vectors`, `/collections/{name}/search` |
| **Root required?** | NO — runs as any user, DB can be stored anywhere |
| **Install to /opt/ruvector/?** | Optional — not required. Default is `./ruvector.db` or `~/.config/ruvector/` |
