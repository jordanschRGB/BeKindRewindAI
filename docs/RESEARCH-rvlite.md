# Research: rvlite — Lightweight Vector DB

**Bead**: bcbcaedc-bb0e-4994-9bfc-297d1ab5e86c
**Agent**: Coral-polecat
**Date**: 2026-04-01

---

## What is rvlite?

RvLite is a **WASM-native, standalone vector database** from the RuVector ecosystem. It is a thin orchestration layer over existing RuVector WASM crates, providing SQL, SPARQL, and Cypher query interfaces for vector operations — all running inside a WebAssembly runtime with no native server required.

### Key characteristics

- **Core engine**: Delegates to `ruvector-core` for vector storage and HNSW search (SIMD-accelerated). One `VectorDB` per SQL table.
- **Query languages**: SQL (CREATE TABLE with VECTOR type, INSERT, SELECT with `<->` distance operator), Cypher (property graph), SPARQL (RDF triple store).
- **Persistence**: IndexedDB in browsers; `rvf-backend` feature for an optional file-backed epoch log (not yet production-ready).
- **Status**: Proof-of-Concept. Version 0.2.0 (lib.rs) / 0.3.0 (Cargo.toml). Core vector + SQL + Cypher + SPARQL are implemented and compile. Full feature integration (GNN, self-learning) is still pending.
- **Size target**: < 3MB gzipped (still unmeasured per README).
- **Distribution**: Rust crate (`crates.io: rvlite v0.3.0`) and NPM packages (`@ruvector/rvlite v0.2.4`, `rvlite v0.2.4`).

### Architecture (from `lib.rs` and submodules)

```
RvLite (WASM)
  ├─ SqlEngine        → wraps ruvector-core VectorDB per table
  ├─ CypherEngine    → in-memory PropertyGraph (nodes + edges)
  ├─ TripleStore     → in-memory RDF triple store (SPARQL)
  └─ IndexedDBStorage → browser persistence
         └─ ruvector-core (HNSW, SIMD vector ops)
```

Supported SQL syntax (from `sql/executor.rs`):
```sql
CREATE TABLE docs (id TEXT PRIMARY KEY, embedding VECTOR(384));
INSERT INTO docs (id, embedding) VALUES ('1', '[...]');
SELECT id, embedding <-> '[...]' AS distance FROM docs ORDER BY distance LIMIT 10;
```

---

## How does it compare to plain HNSW + SQLite?

This is the core question. The alternatives are:

| | **rvlite** | **sqlite-vec / sqlite-vector-rs** | **pgvector** | **hnswlib + custom** |
|---|---|---|---|---|
| **Delivery** | WASM (no native binary) | SQLite extension (.so/.dll) | Postgres extension | Native Rust crate |
| **Server required?** | No (runs in JS runtime) | No | Yes (Postgres) | No |
| **HNSW** | Via ruvector-core | Built-in | Built-in | You implement |
| **SQL interface** | Yes (own parser) | Yes (SQLite) | Yes (SQL) | No |
| **Cross-platform** | Browser/Node/Bun/Edge | Desktop + server | Server only | Desktop + server |
| **Python bindings** | None | `pip install sqlite-vec` | `pip install pgvector` | You write them |
| **Maturity** | POC | Stable (7K GitHub stars) | Stable (production) | Varies |
| **File persistence** | IndexedDB (browser), epoch log (opt-in) | SQLite file | Postgres WAL | You implement |

**Plain HNSW + SQLite** (using sqlite-vec or sqlite-vector-rs) is a **more mature, more portable, and better-tested** option for desktop Mac/Windows deployment. sqlite-vec runs as a SQLite extension loaded at connection time — no server process, no WASM overhead, and it's been in active use since 2024.

**rvlite's advantages** are narrow:
- It runs **inside a browser** without any native layer at all.
- It provides **Cypher and SPARQL** as first-class query languages, which sqlite-vec does not.
- For an already WASM-compiled Rust codebase, rvlite fits naturally in the toolchain.

**rvlite's disadvantages for desktop use**:
- Requires Node.js/Bun/Deno runtime to execute (not a native binary).
- WASM adds ~20-30% latency overhead vs native code for compute-heavy workloads.
- POC status means missing features, unmeasured performance, and no production hardening.
- The `rvf-backend` file persistence is opt-in and not yet stable.

---

## Could it replace the flat file memory backend in BeKindRewindAI?

**Short answer: No — not for the current BeKindRewindAI architecture.**

### Why not

1. **BeKindRewindAI appears to target local desktop Mac/Windows use**. rvlite has no native binary; it runs only in a WASM JS runtime. Deploying it requires Node.js or a browser, adding an entire runtime dependency where none exists today.

2. **No Python bindings**. BeKindRewindAI's pipeline (Whisper transcription, LLM labeling, memory) is likely Python-based. rvlite has no Python API — you would need to shell out to a Node.js subprocess or build PyO3 bindings yourself, adding complexity with no benefit over a native solution.

3. **POC status**. The README explicitly marks rvlite as "Proof of Concept — Architecture Validated." The bundle size is unmeasured, benchmarks are pending, and several features (GNN integration, ReasoningBank, hyperbolic embeddings) are still on the roadmap.

4. **Flat file is simpler for single-machine use**. For a personal AI tool running locally, a flat file or SQLite with sqlite-vec gives you:
   - Zero additional runtimes
   - ACID durability without IndexedDB workarounds
   - A mature, well-understood storage model
   - No WASM overhead

### When rvlite *could* be considered

- If BeKindRewindAI were to add a **browser-based UI** that stores vector memories client-side (e.g., a SvelteKit app with a WASM backend).
- If the toolchain already includes **Node.js/Bun as a deployment target**.
- If the **Cypher graph query API** is specifically needed for memory traversal.

---

## Does it work on Mac/Windows?

**With a runtime: Yes. As a native binary: No.**

| Platform | How it runs |
|---|---|
| **Browser** (Chrome, Firefox, Safari, Edge) | ✅ Native WASM target |
| **Node.js** (Mac, Windows, Linux) | ✅ `@ruvector/rvlite` npm package |
| **Deno** | ✅ WASM import |
| **Bun** | ✅ WASM import |
| **Cloudflare Workers / Vercel Edge** | ✅ WASM-native |
| **Bare Metal Mac/Windows (no JS runtime)** | ❌ No native binary published |

The NPM packages (`@ruvector/rvlite`, `rvlite`) do publish WASM binaries that Node.js can load, so in practice rvlite works on Mac and Windows as long as Node.js is installed. But there is no `rvlite` CLI binary or native library download.

For context: sqlite-vec ships as a `.so` (Linux), `.dylib` (macOS), and `.dll` (Windows) loaded by SQLite — fully native, no runtime needed. That is a meaningfully different deployment story.

---

## Summary

| Question | Answer |
|---|---|
| **What is rvlite?** | WASM-native vector DB wrapping ruvector-core with SQL/Cypher/SPARQL query layers and IndexedDB persistence. POC status. |
| **vs plain HNSW + SQLite?** | rvlite offers more query flexibility (Cypher, SPARQL) and browser portability, but sqlite-vec is more mature, faster (native), and simpler for desktop deployment. |
| **Replace flat file backend?** | No. No native binary, no Python bindings, POC status. Better alternatives exist for local desktop use (sqlite-vec + SQLite file). |
| **Mac/Windows?** | Works via Node.js/Bun/Deno WASM runtime, but no native binary. Not a zero-dependency desktop solution. |

---

## Sources

- `crates/rvlite/src/lib.rs` — main RvLite struct, vector ops, SQL/Cypher/SPARQL dispatch
- `crates/rvlite/src/sql/executor.rs` — SqlEngine with VectorDB per table
- `crates/rvlite/src/cypher/mod.rs` — CypherEngine (property graph)
- `crates/rvlite/src/sparql/mod.rs` — TripleStore + SPARQL executor
- `crates/rvlite/src/storage/indexeddb.rs` — IndexedDB persistence
- `crates/rvlite/Cargo.toml` — dependencies, features, size budget
- `crates/rvlite/README.md` — architecture, roadmap, status
- crates.io: rvlite v0.3.0
- npm: @ruvector/rvlite v0.2.4
