# Research: rvAgent AI Agent Framework

**Bead**: `da0a5fb8-059d-44c1-b179-8d9b2c8518aa`
**Author**: Birch (Archivist)
**Date**: 2026-04-01
**Status**: Complete

---

## TL;DR — The "Geniuinely Insane" Part

Jordan called this "genuinely insane" because RuVector isn't a vector database with agent features bolted on — it's a **complete AI agent operating system** built in Rust. Every crate is self-contained, blazing fast, and designed to work together. The "insane" part is the **sheer scope**: 145+ workspace crates covering everything from Flash Attention to quantum coherence, with an agent orchestration layer (`ruFlo`) that rivals cloud AI platforms — all running locally, mostly on CPU.

But the rvAgent crates the bead references (`rvagent-core`, `rvagent-backends`, `rvagent-mcp`) **do not exist** at the specified paths. The ruvector-browse directory doesn't exist in this rig's workspace. The closest equivalents are different crates with different names.

---

## 1. What is rvAgent? Does it exist?

**Short answer: No — those specific crates don't exist.** The bead references:

```
/workspace/rigs/.../ruvector-browse/crates/rvAgent/rvagent-core/
/workspace/rigs/.../ruvector-browse/crates/rvAgent/rvagent-backends/
/workspace/rigs/.../ruvector-browse/crates/rvAgent/rvagent-mcp/
```

The `ruvector-browse` directory does not exist in this workspace, and no `rvagent-*` crates appear in RuVector's 145+ crate workspace (verified via GitHub listing).

**The RuVector ecosystem does have agent-framework crates — they just use different naming:**

| What the bead calls it | Actual crate(s) | Purpose |
|---|---|---|
| `rvagent-core` | `mcp-gate` + `sona` + `ruvector-tiny-dancer-core` | Core agent runtime, learning, routing |
| `rvagent-backends` | `ruvllm` + provider-specific MCP wrappers | LLM inference backends |
| `rvagent-mcp` | `mcp-gate` + `mcp-brain` + `ruvswarm-mcp` | MCP tool exposure |

The bead may be referencing a **future or renamed** restructuring of these crates, or an external project that uses the `rvagent` namespace.

### What RuVector actually has instead

**`mcp-gate`** (crates/mcp-gate) is the closest to "rvagent-core MCP layer." It's an MCP server for the **Cognitum Gate** — a coherence-verification system that Permit/Defer/Deny actions based on min-cut graph partitioning. Exposes 3 tools:

```rust
// From crates/mcp-gate/src/tools.rs
permit_action(action_id, action_type, target, context) → PermitToken | Defer | Deny
get_receipt(sequence) → WitnessReceipt (cryptographic audit trail)
replay_decision(sequence, verify_chain) → ReplayResult (deterministic audit)
```

**`mcp-brain`** (crates/mcp-brain) is the **shared brain** — cross-session memory sharing via MCP. 20 tools including `brain_share`, `brain_search`, `brain_vote`, `brain_transfer` (cross-domain transfer learning via Thompson Sampling), and Brainpedia wiki-style knowledge pages with evidence tracking.

**`ruvector-tiny-dancer-core`** is the **neural router** — FastGRNN-based routing that decides whether to use cheap or expensive models. Claims 70-85% LLM cost reduction. Sub-millisecond inference (144ns feature extraction, 7.5μs model inference).

---

## 2. How Does the Tool-Use / Subagent System Work?

RuVector doesn't have a single unified tool-use framework — it has **multiple competing tool-infrastructure approaches**:

### A. MCP-based Tool Exposure (3 separate MCP servers)

1. **`mcp-gate`**: Coherence gate tools. stdio JSON-RPC 2.0. Tools: `permit_action`, `get_receipt`, `replay_decision`. Built on `cognitum_gate_tilezero::TileZero` (the 256-tile WASM coherence fabric).

2. **`mcp-brain`**: Shared brain tools. stdio JSON-RPC. 20 tools across 3 categories:
   - Core: `brain_share`, `brain_search`, `brain_get`, `brain_vote`, `brain_transfer`, `brain_drift`, `brain_partition`, `brain_list`, `brain_delete`, `brain_status`, `brain_sync`
   - Brainpedia: `brain_page_create/get/delta/deltas/evidence/promote`
   - WASM Nodes: `brain_node_list/publish/get/wasm/revoke`

3. **`ruvswarm-mcp`** (separate repo: `ruvnet/ruv-FANN`): Swarm orchestration MCP. 11 tools:
   ```
   ruvswarm.spawn, ruvswarm.orchestrate, ruvswarm.query,
   ruvswarm.monitor, ruvswarm.optimize,
   ruvswarm.memory.store, ruvswarm.memory.get,
   ruvswarm.task.create, ruvswarm.workflow.execute,
   ruvswarm.agent.list, ruvswarm.agent.metrics
   ```

### B. RuVector Tool Calling (via ruFlo / agentic-flow)

The actual **agent orchestration** happens in two external repos:

- **`ruFlo`** (29k stars, formerly `claude-flow`): `ruvnet/ruflo` — enterprise multi-agent orchestration for Claude Code. 54+ specialized agents, queen-led swarms with Byzantine fault-tolerant consensus, HNSW memory, 175+ MCP tools.
- **`agentic-flow`**: `ruvnet/agentic-flow` — production agents with Claude Agent SDK. 66 self-learning agents, 213 MCP tools, multi-provider failover.

### C. Neural Routing (not tool-calling per se)

**`ruvector-tiny-dancer-core`** uses FastGRNN (<1MB models, 80-90% sparsity) to route requests to appropriate model tiers. Not a subagent system — it's a **smart load balancer** that decides which model handles a request.

---

## 3. What Backends Does It Support?

**`ruvllm`** crate (crates/ruvllm) — LLM serving runtime:

- **Backend**: Candle + mistral-rs (NOT llama.cpp or vLLM)
- **Models**: GGUF format — Llama 3.x, Qwen 2.5, Mistral, Phi-3, Gemma-2, RuvLTRA
- **Hardware**: Metal (Apple GPU), CUDA, ANE (Apple Neural Engine), WebGPU, WASM, CPU
- **Features**: PagedAttention, KV-cache quantization (TurboQuant 2-4 bit), speculative decoding, continuous batching
- **Performance**: ~88-135 tok/s on M4 Pro for 7B Q4K models

**External API support** (via standard LLM API calls in agent.py):
- OpenAI-compatible API endpoints
- Anthropic
- Local Ollama (via OpenAI-compatible API)

**No native PyO3 bindings** — Python access is only through:
1. `npm install @ruvector/ruvllm` — Node.js bindings
2. `ruvllm-cli` subprocess wrapper
3. HTTP REST API (ruvector-server)

---

## 4. How Does rvagent-mcp Expose Tools via MCP?

Since `rvagent-mcp` doesn't exist, here's how the **actual MCP crates** work:

### `mcp-gate` Protocol

```json
// Initialize
→ {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05"}}
← {"jsonrpc":"2.0","id":1,"result":{"capabilities":{"tools":{}},"serverInfo":{"name":"mcp-gate","version":"0.1.0"}}}

// List tools
→ {"jsonrpc":"2.0","id":2,"method":"tools/list"}
← {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"permit_action",...},{"name":"get_receipt",...},{"name":"replay_decision",...}]}}

// Call tool
→ {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"permit_action","arguments":{...}}}
```

### `mcp-brain` Protocol (Federated Brain)

```
Claude Code ← stdio JSON-RPC → mcp-brain (local) ← HTTPS REST API → mcp-brain-server (π.ruv.io Cloud Run)
```

The federated brain learns across all Claude Code sessions. Every `brain_share` embeds the learning, strips PII, and signs it with SHAKE-256 witness hashing. Quality improves via **Bayesian voting** (`brain_vote`) and **cross-domain transfer learning** via Thompson Sampling (`brain_transfer`).

### `ruvswarm-mcp` (RUV Swarm)

Uses `rmcp` (official Rust MCP SDK), axum web framework, WebSocket + stdio transport. Full JSON-RPC 2.0 with session management, performance metrics, and real-time event streaming.

---

## 5. Could This Replace BeKindRewindAI's `harness/agent.py` Entirely?

**No — not directly, and not without significant work.** Here's why:

### What BeKindRewindAI Does

BeKindRewindAI's `harness/agent.py` implements a **three-agent architecture** (Catcher/Grader/Dreamer) using **smolagents** with an **OpenAI-compatible API**:

1. **Archivist**: Conversational interface, drives pipeline. Has conversation history + memory.
2. **Worker**: Generates vocabulary + labels. Isolated context (skill briefing + transcript + last score).
3. **Scorer**: Rates quality 1-10, states human consequences. Isolated context (transcript + label only).

The **orchestrator.py** wraps these with tools: `detect_devices`, `start_capture`, `stop_capture`, `encode_video`, `transcribe_video_file`, `label_tape`, `score_label`, `save_tape_metadata`, `read_memory`, `save_to_memory`.

### What RuVector Could Replace

| Component | RuVector Equivalent | Can It Replace? |
|---|---|---|
| smolagents orchestration | ruFlo / agentic-flow | **Partial** — these are Claude Code orchestration platforms, not Python libraries |
| Archivist conversation | ruFlo agents | **Partial** — 54+ Claude Code agents, but not a local VHS-focused conversational agent |
| Worker (vocabulary) | sona trajectory learning | **No** — sona is for LLM routing, not Whisper vocabulary generation |
| Scorer (quality rating) | prime-radiant coherence engine | **Partial** — prime-radiant detects hallucinations/coherence, but doesn't do the specific label scoring rubric |
| Memory (RuVector HNSW) | harness/memory.py already uses RuVector | **Already using it** — via `mcporter` CLI to `ruvector.vector_db_*` |
| Local LLM inference | ruvllm (GGUF) | **Yes, technically** — but requires Python wrapper around `ruvllm-cli` subprocess |
| Agent routing/cost reduction | ruvector-tiny-dancer-core | **Yes for routing** — but not used in BeKindRewindAI pipeline |

### The Core Problem

BeKindRewindAI's three-agent isolation pattern (scorer never sees conversation, worker never sees history) is a **specific design choice** for VHS transcription quality. RuVector's agent crates (`mcp-gate`, `mcp-brain`) are **general-purpose** — they don't implement this isolation pattern out of the box.

The `sona` learning engine is genuinely impressive — MicroLoRA adaptation in <1ms with EWC++ anti-forgetting — but it's designed for **LLM router optimization**, not Whisper vocabulary priming.

### Verdict

RuVector **cannot replace** BeKindRewindAI's harness/agent.py because:
1. The rvagent crates don't exist
2. RuFlo/agentic-flow are Claude Code orchestration platforms, not drop-in Python replacements
3. The VHS-specific pipeline (vocabulary priming → capture → transcribe → label → score → retry) is bespoke
4. The three-agent isolation pattern is a quality engineering choice RuVector doesn't replicate

RuVector **could augment** BeKindRewindAI in specific areas:
- `ruvllm` for local GGUF inference (replacing OpenAI API calls)
- `prime-radiant` for hallucination detection in transcripts
- `ruvector-tiny-dancer-core` for routing transcription tasks to appropriate model tiers

---

## 6. What's the Learning Loop — Does It Improve Over Time?

**Yes — and in ways BeKindRewindAI doesn't.**

### BeKindRewindAI's Learning

- **RuVector HNSW** for semantic memory search (already integrated via `harness/memory.py`)
- **Biomimetic decay**: frequently-accessed terms reinforce, one-off words fade
- **Flat markdown** file as human-readable backup
- **No model weight updates** — purely retrieval-based

### RuVector's Learning (via `sona` crate)

**Three-tier continuous learning:**

| Tier | Mechanism | Speed | What It Does |
|---|---|---|---|
| Instant | MicroLoRA | ~45μs | Per-request weight adjustments from immediate feedback |
| Session | GNN attention updates | <1ms | Reinforces paths that led to good results during session |
| Long-term | EWC++ consolidation | ~100ms background | Permanently strengthens patterns without forgetting old ones |

**EWC++ (Elastic Weight Consolidation)** is the key innovation — it solves catastrophic forgetting by protecting important weights when learning new patterns. BeKindRewindAI has no equivalent.

**ReasoningBank**: K-means++ clustered pattern library. Successful interaction patterns are stored and retrieved to inform future decisions. BeKindRewindAI has nothing like this.

**Trajectory Tracking**: Records full path of each interaction (query → model choice → outcome → quality score). Every user session becomes training data automatically.

**Cross-session via `mcp-brain`**: Federated learning across all Claude Code sessions. Brain voting, Thompson Sampling transfer learning, drift detection.

### The Comparison

BeKindRewindAI's memory is **retrieval-only** — it stores and finds past vocabulary/sessions but doesn't update any model weights. RuVector's `sona` continuously **adapts model weights** in real-time using feedback signals.

If BeKindRewindAI implemented `sona`, it could learn things like:
- Which vocabulary terms consistently improve transcription quality
- Which domain presets work best for certain tape types
- Optimal tape-count estimates based on session patterns
- When to retry labeling vs. accept a lower score

---

## Why Jordan Called It "Genuinely Insane"

1. **145+ Rust crates** in one self-learning system — vector DB, GNN, LLM runtime, MCP server, coherence verification, WASM runtime, cognitive containers, FPGA acceleration, quantum error correction, genomic analysis

2. **The Cognitum Gate** (mcp-gate) uses **min-cut graph partitioning** for AI safety decisions. Every Permit/Defer/Deny generates a **cryptographically signed witness receipt** with hash-chain audit trail.

3. **Sub-millisecond learning**: MicroLoRA adaptation in 45μs, GNN re-ranking in <1ms, full session adaptation in ~10ms — while BeKindRewindAI's learning is purely retrieval-based.

4. **Hardware-optional AI**: Runs on CPU (preferring it), with GPU/ANE/CUDA as burst acceleration. BeKindRewindAI's Whisper already runs local.

5. **SONA + EWC++**: The only production system that continuously learns from feedback WITHOUT forgetting and WITHOUT cloud APIs. The learning is inside the Rust binary.

6. **The shared brain (`mcp-brain`)**: Federated cross-session learning for Claude Code. Every session contributes to a collective intelligence with Bayesian quality scoring.

---

## Summary Table

| Question | Answer |
|---|---|
| Does rvAgent exist? | No. The crates don't exist at the specified paths. Closest equivalents use different naming. |
| Full replacement for 3-agent? | No. No direct replacement for Archivist/Worker/Scorer pattern. |
| Tool-use system? | MCP-based (3 servers: mcp-gate, mcp-brain, ruvswarm-mcp) + ruFlo orchestration |
| Backends? | GGUF via ruvllm (Candle+mistral-rs), OpenAI, Anthropic, Ollama |
| MCP exposure? | Yes, via stdio JSON-RPC 2.0 across all three MCP crates |
| Replace harness/agent.py? | No — bespoke VHS pipeline, smolagents-based, specific agent isolation pattern |
| Learning loop? | Yes — far more sophisticated than BeKindRewindAI. MicroLoRA+GN+EWC++ with cross-session federated learning via mcp-brain |
