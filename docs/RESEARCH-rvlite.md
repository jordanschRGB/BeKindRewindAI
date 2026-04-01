# Research: rvlite — Lightweight Vector DB Alternative

**Date:** 2026-04-01
**Bead:** 52b4037e-97e3-49a7-a577-b17224f252d3
**Agent:** Drift

## 1. What rvlite Is

**rvlite** (RvLite) is a **WASM-powered standalone vector database** from the RuVector project. It is NOT a native Rust crate you link against — it compiles to WebAssembly and runs in browsers, Node.js, Deno, Bun, Cloudflare Workers, and Vercel Edge Functions.

Key defining characteristic: **it runs ENTIRELY client-side with no server required**. Data persists in IndexedDB (browser) or similar storage backends.

Architecture: thin orchestration layer over existing RuVector WASM crates:
- `ruvector-core` — vectors + SIMD distance
- `ruvector-wasm` — storage/indexing bindings
- `ruvector-graph-wasm` — Cypher property graph
- `ruvector-gnn-wasm` — GNN layers
- `sona` — self-learning ReasoningBank
- `micro-hnsw-wasm` — ultra-fast HNSW

**Current status: Proof of Concept (v0.1.0)** per the README. The NPM package `@ruvector/rvlite` is at v0.2.4 but the Rust crate is at v0.3.0. Both show recent updates (late 2025 / early 2026).

## 2. What "Lightweight Vector DB" Means Here

"Lightweight" in rvlite's context means:

| Aspect | Full RuVector | rvlite |
|--------|--------------|--------|
| Deployment | Server + client | Zero-deploy, in-browser |
| Dependencies | PostgreSQL, Redis, etc. | None — pure WASM |
| Persistence | External DB | IndexedDB |
| Bundle size | N/A (native) | ~850KB WASM (~300KB gzipped) |
| Multi-user | Yes (server) | No (single-user, browser-local) |
| Query languages | SQL + graph + more | SQL + SPARQL + Cypher (same) |
| GNN support | Full | Via ruvector-gnn-wasm |

The "lightweight" claim is specifically about **deployment footprint** — you don't need a server at all. It's the difference between deploying a database server vs. shipping a JavaScript bundle.

## 3. Comparison to Full RuVector vs. Standalone hnsw_rs

### rvlite vs. Full RuVector

rvlite reuses most of the same underlying crates (ruvector-core, etc.) but wraps them in WASM instead of running them as a native server. The vector search quality should be nearly identical since the core HNSW implementation is the same.

Differences:
- **No server overhead** — rvlite runs in-process in the browser
- **No network latency** — queries are local
- **Single-user only** — no connection pooling, no multi-client sync
- **Memory bounded by browser** — typically 2-4GB max vs. dedicated server
- **IndexedDB persistence** vs. REDB/memmap on the full server

### rvlite vs. standalone hnsw_rs

`hnsw_rs` is a pure Rust HNSW implementation that ruvector-core uses internally. It is a building block, not a database:

| | rvlite | hnsw_rs |
|--|--------|---------|
| Level | Complete database | Algorithm library |
| Query interfaces | SQL, SPARQL, Cypher | Rust API only |
| Persistence | IndexedDB | You build it |
| Language | Any via WASM | Rust only |
| Use case | End-user product | Internal crate |

rvlite is to hnsw_rs roughly what SQLite is to a B-tree implementation.

## 4. Cross-Platform Support

**Native platforms (rvlite WASM runs on):**
- ✅ Chrome 89+
- ✅ Firefox 89+
- ✅ Safari 15+
- ✅ Edge 89+
- ✅ Node.js 18+
- ✅ Deno
- ✅ Bun
- ✅ Cloudflare Workers
- ✅ Vercel Edge Functions

**No native Mac/Windows binaries** — rvlite is WASM-only. You cannot `cargo install rvlite` and run it as a CLI tool on Mac or Windows. It runs through the WASM runtime in the browser or Node.js.

**Platform targets for Rust crate (crates.io):**
- `x86_64-unknown-linux-gnu`
- `x86_64-pc-windows-msvc`
- `i686-pc-windows-msvc`
- `aarch64-apple-darwin`
- `aarch64-unknown-linux-gnu`

These are the platforms the Rust crate compiles for, but rvlite's value proposition is WASM, not native binaries.

## 5. Python Bindings

**No native Python bindings.** rvlite is accessed via:
- JavaScript/TypeScript NPM: `@ruvector/rvlite`
- Direct WASM import in browser

For Python access to RuVector stack, you would need:
- `@ruvector/core` NPM package (Node.js native bindings, not PyO3)
- HTTP REST API via `ruvector-server` (requires Docker/server)
- Direct use of `ruvector-core` Rust crate via PyO3 (you'd need to write bindings)

**Python is NOT a first-class citizen here.** The RuVector ecosystem is primarily Rust + JavaScript/TypeScript.

## 6. Can rvlite Replace RuVector for Mac/Windows BeKindRewindAI Deployment?

**Short answer: No — not directly, and not without significant tradeoffs.**

Here's why:

### Problems with rvlite for BeKindRewindAI

1. **No Python bindings** — BeKindRewindAI is Python-based (Flask, faster-whisper, etc.). rvlite is JavaScript/WASM only. There is no Python API for rvlite.

2. **WASM runs in a sandbox** — You cannot access local filesystem, capture cards, or system hardware from WASM. The pipeline.py records video via ffmpeg — that cannot happen in a WASM runtime.

3. **Memory constraints** — Browser WASM is typically limited to 2-4GB. A large vocabulary corpus + embedding index could hit this limit, especially with multiple recordings.

4. **No native binaries** — rvlite has no `cargo install` path for Mac/Windows CLI use. It's WASM-only.

5. **Single-user, single-browser** — rvlite's IndexedDB persistence is per-browser, not a shared database across app restarts in a predictable location.

### What Could Work

If the goal is "simple Mac/Windows deployment without Docker":

- **Option A: `ruvector-server` via Docker** (already researched by another agent — Docker is the practical path)
- **Option B: Embed `ruvector-core` directly** in a Python-native way via PyO3 — but this requires writing Rust/Python bindings
- **Option C: Use a different vector DB** purpose-built for local Python — like `faiss-cpu`, `chromadb`, or `qdrant-client` (these have native Python support)

rvlite is excellent for **browser-based or edge deployments** where you need a zero-infrastructure vector database. It is not suited for a Python desktop app that needs to interface with local hardware (capture cards) and existing Python tooling.

## Verdict

**Relevance to BeKindRewindAI: Low.**

rvlite solves a different problem — client-side embedded vector database for browser/edge. BeKindRewindAI needs a server-side or Python-native vector store that can:
1. Run on Mac/Windows without Docker
2. Interface with Python (the app is Python)
3. Handle potentially large indices
4. Persist to a known filesystem location

For simple Mac/Windows deployment, `ruvector-server` via Docker (per the other research bead) or a pure Python vector DB like FAISS or ChromaDB would be more appropriate. rvlite is architecturally interesting but not a fit for this use case.
