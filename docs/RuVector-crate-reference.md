# RuVector Crate Reference

Personal reference document listing all RuVector Cargo crates with one-line descriptions and categories.

**Categories:** vector-search, memory-graph, llm-inference, agent-orchestration, encoding, networking, storage, utils, experimental

---

## Core Crates

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-core` | vector-search | High-performance Rust vector database core with HNSW indexing |
| `ruvector-node` | vector-search | Node.js bindings for Ruvector via NAPI-RS |
| `ruvector-wasm` | vector-search | WASM bindings for Ruvector including kernel pack system |
| `ruvector-cli` | vector-search | CLI and MCP server for Ruvector |
| `ruvector-bench` | utils | Comprehensive benchmarking suite for Ruvector |
| `ruvector-metrics` | utils | Prometheus-compatible metrics collection for Ruvector |
| `ruvector-filter` | vector-search | Advanced metadata filtering for Ruvector vector search |
| `ruvector-collections` | storage | High-performance collection management for Ruvector vector databases |
| `ruvector-cluster` | storage | Distributed clustering and sharding for ruvector |
| `ruvector-raft` | storage | Raft consensus implementation for ruvector distributed metadata |
| `ruvector-replication` | storage | Data replication and synchronization for ruvector |
| `ruvector-server` | networking | High-performance REST API server for Ruvector |
| `ruvector-snapshot` | storage | Point-in-time snapshots and backup for Ruvector |

---

## Router Crates

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-router-core` | agent-orchestration | Core vector database and neural routing inference engine |
| `ruvector-router-cli` | agent-orchestration | CLI for testing and benchmarking ruvector-router-core |
| `ruvector-router-ffi` | agent-orchestration | NAPI-RS bindings for ruvector-router-core |
| `ruvector-router-wasm` | agent-orchestration | WASM bindings for ruvector-router-core |

---

## Tiny Dancer (Agent Routing)

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-tiny-dancer-core` | agent-orchestration | Production-grade AI agent routing system with FastGRNN neural inference |
| `ruvector-tiny-dancer-wasm` | agent-orchestration | WASM bindings for Tiny Dancer neural routing |
| `ruvector-tiny-dancer-node` | agent-orchestration | Node.js bindings for Tiny Dancer neural routing |

---

## Graph & GNN

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-graph` | memory-graph | Distributed Neo4j-compatible hypergraph database with SIMD optimization |
| `ruvector-graph-node` | memory-graph | Node.js bindings for RuVector Graph Database |
| `ruvector-graph-wasm` | memory-graph | WebAssembly bindings for RuVector graph database |
| `ruvector-gnn` | memory-graph | Graph Neural Network layer for Ruvector on HNSW topology |
| `ruvector-gnn-node` | memory-graph | Node.js bindings for Ruvector GNN |
| `ruvector-gnn-wasm` | memory-graph | WebAssembly bindings for RuVector GNN |
| `ruvector-graph-transformer` | memory-graph | Unified graph transformer with 8 verified modules for physics, bio, manifold, temporal, economic |
| `ruvector-graph-transformer-wasm` | memory-graph | WASM bindings for ruvector-graph-transformer |
| `ruvector-graph-transformer-node` | memory-graph | Node.js bindings for RuVector Graph Transformer |

---

## Attention Mechanisms

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-attention` | llm-inference | Attention mechanisms for ruvector - geometric, graph, and sparse attention |
| `ruvector-attention-wasm` | llm-inference | WebAssembly attention mechanisms: Multi-Head, Flash, Hyperbolic, MoE, CGT Sheaf |
| `ruvector-attention-node` | llm-inference | Node.js bindings for ruvector-attention |
| `ruvector-attention-unified-wasm` | llm-inference | Unified WASM bindings for 18+ attention mechanisms |

---

## CNN

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-cnn` | encoding | CNN feature extraction for image embeddings with SIMD acceleration |
| `ruvector-cnn-wasm` | encoding | WASM bindings for ruvector-cnn |

---

## MinCut (Dynamic Graph Analysis)

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-mincut` | vector-search | Subpolynomial dynamic min-cut for self-healing networks and AI optimization |
| `ruvector-mincut-wasm` | vector-search | WASM bindings for subpolynomial-time dynamic minimum cut |
| `ruvector-mincut-node` | vector-search | Node.js bindings for subpolynomial-time dynamic minimum cut |
| `ruvector-mincut-gated-transformer` | llm-inference | Ultra low latency transformer inference with mincut-gated coherence control |
| `ruvector-mincut-gated-transformer-wasm` | llm-inference | WASM bindings for mincut-gated transformer inference |
| `ruvector-attn-mincut` | llm-inference | Min-cut gating attention operator - dynamic graph-based alternative to softmax |

---

## LLM Inference

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvllm` | llm-inference | LLM serving runtime with Ruvector integration - Paged attention, KV cache, SONA learning |
| `ruvllm-cli` | llm-inference | CLI for RuvLLM model management and inference |
| `ruvllm-wasm` | llm-inference | WASM bindings for RuvLLM with WebGPU acceleration |
| `ruvector-sparse-inference` | llm-inference | PowerInfer-style sparse inference engine for edge devices |

---

## Math & Solvers

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-math` | utils | Advanced mathematics: Optimal Transport, Information Geometry, Product Manifolds |
| `ruvector-math-wasm` | utils | WASM bindings for ruvector-math |
| `ruvector-solver` | utils | Sublinear-time solver: O(log n) to O(sqrt(n)) for sparse linear systems, PageRank |
| `ruvector-solver-wasm` | utils | WASM bindings for RuVector sublinear-time solver |
| `ruvector-solver-node` | utils | Node.js NAPI bindings for RuVector sublinear-time solver |

---

## Storage & Database

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-postgres` | storage | PostgreSQL extension - pgvector drop-in replacement with 230+ SQL functions |
| `ruvector-delta-core` | storage | Core delta types for behavioral vector change tracking |
| `ruvector-delta-wasm` | storage | WASM bindings for delta operations on vectors |
| `ruvector-delta-index` | storage | Delta-aware HNSW index with incremental updates |
| `ruvector-delta-graph` | storage | Delta operations for graph structures |
| `ruvector-delta-consensus` | storage | Distributed delta consensus using CRDTs and causal ordering |

---

## DAG & Workflows

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-dag` | agent-orchestration | Directed Acyclic Graph structures for query plan optimization |
| `ruvector-dag-wasm` | agent-orchestration | Minimal WASM DAG library for browser and embedded |

---

## Nervous System (Bio-Inspired AI)

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-nervous-system` | llm-inference | Bio-inspired neural system with spiking networks, BTSP learning, EWC plasticity |
| `ruvector-nervous-system-wasm` | llm-inference | WASM bindings for bio-inspired AI components |

---

## FPGA & Hardware

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-fpga-transformer` | llm-inference | FPGA Transformer backend with deterministic latency and coherence gating |
| `ruvector-fpga-transformer-wasm` | llm-inference | WASM bindings for FPGA Transformer backend |

---

## Coherence & Verification

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-coherence` | utils | Coherence measurement proxies for comparing attention mechanisms |
| `ruvector-profiler` | utils | Memory, power, and latency profiling hooks for benchmarking |
| `ruvector-verified` | utils | Formal verification layer with proof-carrying vector operations |
| `ruvector-verified-wasm` | utils | WASM bindings for proof-carrying vector operations |
| `prime-radiant` | utils | Coherence engine using sheaf Laplacian for AI safety and hallucination detection |

---

## Domain Expansion & Learning

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-domain-expansion` | llm-inference | Cross-domain transfer learning engine: Rust synthesis, structured planning |
| `ruvector-domain-expansion-wasm` | llm-inference | WASM bindings for domain expansion |
| `ruvector-cognitive-container` | experimental | Verifiable WASM cognitive container with canonical witness chains |
| `ruvector-learning-wasm` | llm-inference | Ultra-fast MicroLoRA adaptation for WASM (<100us latency) |

---

## Sparsifier & Consciousness

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-sparsifier` | vector-search | Dynamic spectral graph sparsification for real-time graph analytics |
| `ruvector-sparsifier-wasm` | vector-search | WASM bindings for dynamic spectral graph sparsification |
| `ruvector-consciousness` | experimental | IIT Phi computation, causal emergence, effective information |
| `ruvector-consciousness-wasm` | experimental | WASM bindings for consciousness metrics |

---

## Temporal & Quantum

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-temporal-tensor` | encoding | Temporal tensor compression with tiered quantization |
| `ruQu` | experimental | Classical nervous system for quantum machines via dynamic min-cut |
| `ruqu-core` | experimental | High-performance quantum circuit simulator in pure Rust |
| `ruqu-algorithms` | experimental | Production-ready quantum algorithms: VQE, Grover, QAOA, Surface Code |
| `ruqu-wasm` | experimental | Run quantum simulations in the browser via WASM |
| `ruqu-exotic` | experimental | Experimental quantum-classical hybrid algorithms |
| `ruvector-crv` | experimental | CRV protocol integration for signal-line methodology |

---

## Economy & Exotic

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-economy-wasm` | experimental | CRDT-based autonomous credit economy for distributed compute networks |
| `ruvector-exotic-wasm` | experimental | Exotic AI mechanisms: Neural Autonomous Orgs, Morphogenetic Networks, Time Crystals |

---

## Robotics & Thermodynamics

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvector-robotics` | experimental | Cognitive robotics platform with perception pipeline and MCP tools |
| `thermorust` | experimental | Thermodynamic neural motif engine with Landauer dissipation and Langevin noise |
| `ruvector-dither` | encoding | Deterministic low-discrepancy dithering for low-bit quantization |

---

## Neural Trader

| Crate | Category | Description |
|-------|----------|-------------|
| `neural-trader-core` | experimental | Canonical market event types, ingest pipeline, and graph schema |
| `neural-trader-coherence` | experimental | MinCut coherence gate, CUSUM drift detection for trading |
| `neural-trader-replay` | experimental | Witnessable replay segments, RVF serialization, audit receipts |
| `neural-trader-wasm` | experimental | WASM bindings for Neural Trader |

---

## MCP & Gate

| Crate | Category | Description |
|-------|----------|-------------|
| `mcp-gate` | agent-orchestration | MCP server for the Anytime-Valid Coherence Gate |
| `mcp-brain` | agent-orchestration | MCP server for RuVector Shared Brain |
| `mcp-brain-server` | networking | Cloud Run backend for Shared Brain with Firestore + GCS |

---

## Cognitum (Gate Kernel)

| Crate | Category | Description |
|-------|----------|-------------|
| `cognitum-gate-kernel` | utils | No-std WASM kernel for 256-tile coherence gate fabric |
| `cognitum-gate-tilezero` | utils | Native arbiter for TileZero in the Coherence Gate |

---

## RuVix (Cognition Kernel)

| Crate | Category | Description |
|-------|----------|-------------|
| `ruvix-types` | experimental | No-std kernel interface types for RuVix Cognition Kernel |
| `ruvix-region` | experimental | Memory region management for RuVix Kernel |
| `ruvix-queue` | experimental | io_uring-style ring buffer IPC for RuVix Kernel |
| `ruvix-cap` | experimental | seL4-inspired capability management for RuVix Kernel |
| `ruvix-proof` | experimental | Proof engine with 3-tier routing for RuVix Kernel |
| `ruvix-sched` | experimental | Coherence-aware scheduler for RuVix Kernel |
| `ruvix-boot` | experimental | RVF boot loading for RuVix Kernel |
| `ruvix-vecgraph` | experimental | Kernel-resident vector and graph stores for RuVix Kernel |
| `ruvix-nucleus` | experimental | Integration crate for RuVix Kernel - syscall dispatch, deterministic replay |
| `ruvix-hal` | experimental | Hardware Abstraction Layer for RuVix Kernel |
| `ruvix-aarch64` | experimental | AArch64 support for RuVix Kernel |
| `ruvix-drivers` | experimental | Device drivers for RuVix Kernel |

---

## rvAgent (AI Agent Framework)

| Crate | Category | Description |
|-------|----------|-------------|
| `rvagent-core` | agent-orchestration | Typed agent state, config, model resolution, agent graph |
| `rvagent-backends` | agent-orchestration | Filesystem, shell, composite, state, store, sandbox protocols |
| `rvagent-middleware` | agent-orchestration | Pipeline, todolist, filesystem, subagents, summarization, memory |
| `rvagent-tools` | agent-orchestration | Tool implementations: ls, read, write, edit, glob, grep, execute, todos |
| `rvagent-subagents` | agent-orchestration | Spec compilation, builder, orchestration, result validation |
| `rvagent-cli` | agent-orchestration | Terminal coding agent with TUI, session management, MCP tools |
| `rvagent-acp` | networking | Agent Communication Protocol with auth, rate limiting, TLS |
| `rvagent-mcp` | agent-orchestration | Model Context Protocol tools, resources, and transport layer |
| `rvagent-wasm` | agent-orchestration | Browser and Node.js agent execution |

---

## Special

| Crate | Category | Description |
|-------|----------|-------------|
| `sona` | llm-inference | Self-Optimizing Neural Architecture for LLM routing with two-tier LoRA |
| `rvlite` | vector-search | Standalone vector database with SQL, SPARQL, Cypher via WASM |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| vector-search | 14 |
| memory-graph | 9 |
| llm-inference | 16 |
| agent-orchestration | 15 |
| encoding | 3 |
| networking | 3 |
| storage | 9 |
| utils | 10 |
| experimental | 22 |
| **Total** | **~101** |

---

*Generated from Cargo.toml descriptions, README files, and repository analysis.*
