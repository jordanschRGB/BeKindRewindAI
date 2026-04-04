# Research: rvlite (lightweight vector DB)

**Bead**: `bcbcaedc-bb0e-4994-9bfc-297d1ab5e86c`
**Researcher**: Ember
**Date**: 2026-04-04

---

## TL;DR

**rvlite is a proof-of-concept WASM orchestration layer** that wraps multiple RuVector WASM crates (core, graph, GNN, HNSW, sona) behind a unified SQL/SPARQL/Cypher API. It runs in browsers, Node.js, Deno, Bun, and edge runtimes. **Status is v0.1.0 POC — not production-ready.** It cannot yet replace the flat file memory backend in BeKindRewindAI.

---

## What is rvlite?

RvLite (RuVector Lite) is a standalone vector database from the [RuVector project](https://github.com/ruvnet/RuVector) that runs **entirely in WebAssembly**. It is a thin orchestration layer (~100KB orchestration overhead) that reuses existing battle-tested WASM crates:

| Dependency | Role |
|---|---|
| `ruvector-core` | Vector ops + SIMD |
| `ruvector-wasm` | Storage + indexing |
| `ruvector-graph-wasm` | Cypher graph queries |
| `ruvector-gnn-wasm` | GNN layers |
| `sona` | Self-learning / ReasoningBank |
| `micro-hnsw-wasm` | Ultra-lightweight HNSW |

Target bundle: **< 3MB gzipped total**. Published on [crates.io as v0.3.1](https://crates.io/crates/rvlite) and as [@ruvector/rvlite on npm](https://www.npmjs.com/package/rvlite) (v0.2.4).

### Query interfaces offered
- **SQL** — vector search via standard SQL with a `VECTOR` type
- **Cypher** — graph traversal queries (property graph)
- **SPARQL** — RDF triple-store queries

### Cross-platform support
RvLite explicitly targets:
- ✅ Browsers (Chrome, Firefox, Safari, Edge)
- ✅ Node.js
- ✅ Deno
- ✅ Bun
- ✅ Cloudflare Workers
- ✅ Vercel Edge Functions

**Mac/Windows**: Yes — via Node.js/Deno/Bun runtimes, or directly in any browser. The WASM runtime is platform-agnostic.

---

## How does it compare to plain HNSW + SQLite?

This is the key comparison for BeKindRewindAI.

| Dimension | rvlite (POC) | Plain HNSW + SQLite |
|---|---|---|
| **Maturity** | v0.1.0 — proof of concept | Mature (sqlite-vss has ~2K stars, sqlite-vec, etc.) |
| **HNSW implementation** | `micro-hnsw-wasm` (standalone crate) | hnswlib, Faiss via sqlite-vss, or native |
| **Storage** | WASM-managed (backed by ruvector-wasm) | Raw SQLite file |
| **Query API** | SQL + Cypher + SPARQL unified | SQL only (or application-level) |
| **Python access** | Via npm/WASM (not native) | Full Python ecosystem (sqlite3, SQLAlchemy) |
| **Graph queries** | Native Cypher via ruvector-graph-wasm | Not native (requires application layer) |
| **Benchmarks** | **None published** | Available (sqlite-vss, sqlite-vec comparisons) |
| **ACID compliance** | Unknown / depends on WASM storage adapter | Full SQLite ACID |
| **Production readiness** | ❌ Not ready | ✅ Yes |
| **Bundle size risk** | ~2.3MB gzipped (all crates) | 0KB (uses existing SQLite install) |

**Plain HNSW + SQLite is the clear winner today** for server/desktop Python applications. The established toolchain (`sqlite-vss` + `hnswlib` + Python) is debugged, benchmarked, and production-proven. rvlite's architecture is compelling but unproven.

---

## Could rvlite replace the flat file memory backend in BeKindRewindAI?

**Short answer: Not yet.**

BeKindRewindAI's flat file memory backend stores vocabulary lists, transcripts, and agent state as plain files (JSON/markdown). The Archivist agent reads/writes these for the memory loop.

Replacing flat files with a vector DB would give:
- Fast semantic similarity search over vocabulary/transcripts
- Structured queries (SQL) instead of text parsing
- Graph relationships (Cypher) for memory tracing

**Why rvlite can't replace it yet:**
1. **POC status** — integration with WASM crates is "pending" according to the README
2. **No Python native binding** — BeKindRewindAI appears to be Python-based; rvlite is WASM-first (Node.js/npm), not PyPI
3. **No benchmarks** — can't evaluate recall/latency vs flat files
4. **Bundle size** — 2.3MB+ WASM is heavy vs a few JSON files
5. **ACID/可靠性** — flat files are simple and battle-tested for this use case

**If/when rvlite matures**, it could consolidate:
- Vocabulary vector search (replacing flat file lookups)
- Session/transcript storage (SQL)
- Memory graph traversal (Cypher — "who said what when")

But today: **use sqlite-vss or sqlite-vec for Python-based local vector search**, which is production-ready and avoids the WASM overhead.

---

## Recommendations

1. **Do not use rvlite for BeKindRewindAI today** — POC, no Python bindings, no benchmarks.
2. **Consider `sqlite-vss`** (Faiss-backed HNSW in SQLite, Python-friendly) or **`sqlite-vec`** (pure C, lighter) as lightweight local vector DB replacements for flat files.
3. **Monitor rvlite** — if it reaches v1.0 with benchmarks and Python bindings, it could be a "one WASM file does everything" solution (SQL + vectors + graphs + GNN) that would be compelling for the memory backend.
4. **Mac/Windows**: Both are fully supported via Node.js/Deno/Bun runtimes.

---

## Sources
- RuVector GitHub: https://github.com/ruvnet/RuVector
- rvlite README: https://github.com/ruvnet/RuVector/blob/main/crates/rvlite/README.md
- crates.io: https://crates.io/crates/rvlite
- npm: https://www.npmjs.com/package/rvlite
- sqlite-vss: https://github.com/asg017/sqlite-vss
- sqlite-vec: https://github.com/sqliteai/sqlite-vector
- Vector DB comparison 2026: https://www.groovyweb.co/blog/vector-database-comparison-2026
