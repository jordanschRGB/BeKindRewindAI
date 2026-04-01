# Research: rvagent

**Date:** 2026-04-01
**Bead:** 7d631626-6654-4554-87f9-45ba28d4e6ad
**Agent:** Wren

## What rvagent Is

rvagent is a **multi-agent AI framework** from RuVector written in Rust — a conversion/rewrite of the DeepAgents project. It provides typed agent state, configurable backends, a middleware pipeline system, and tool abstractions for building autonomous agentic workflows.

The framework consists of 9 crates:

| Crate | Description |
|-------|-------------|
| `rvagent-core` | Typed agent state, config, model resolution, agent graph — the foundation all other crates depend on |
| `rvagent-backends` | Backend protocols: filesystem, shell, composite state, store, sandbox — handles I/O operations |
| `rvagent-middleware` | Pipeline middleware: todolist, filesystem, subagents, summarization, memory, skills, prompt caching, HITL (Human-In-The-Loop), witness, tool sanitizer. Optional SONA/HNSW integration |
| `rvagent-tools` | Tool implementations: ls, read, write, edit, glob, grep, execute, todos, task — enum dispatch pattern |
| `rvagent-subagents` | Subagent orchestration: spec compilation, builder, result validation — spawns child agents from specs |
| `rvagent-cli` | Terminal coding agent with TUI, session management, MCP tools — the main CLI binary |
| `rvagent-acp` | Agent Communication Protocol server — auth, rate limiting, TLS, Axum-based HTTP |
| `rvagent-mcp` | Model Context Protocol tools, resources, and transport layer — SSE transport via Axum |
| `rvagent-wasm` | WASM bindings for browser/Node.js agent execution |

## Agent Orchestration Capabilities

1. **Typed agent graph** (`rvagent-core`): Agents are structured nodes in a graph with typed state and configurable transitions
2. **Subagent system** (`rvagent-subagents`): Spawns child agents from compiled specs with result validation
3. **Middleware pipeline** (`rvagent-middleware`): Chainable middleware for logging, memory, skills, HITL, summarization, tool sanitization
4. **Multiple backend support** (`rvagent-backends`): Filesystem, shell, sandbox, composite state, store backends
5. **Tool enum dispatch** (`rvagent-tools`): Structured tool calls with ls/read/write/edit/glob/grep/execute/todos/task
6. **MCP integration** (`rvagent-mcp`): Model Context Protocol server mode for tool/resource exposure
7. **ACP server** (`rvagent-acp`): Agent Communication Protocol with auth and rate limiting

## Comparison to BeKindRewindAI's 3-Agent Pipeline

| Aspect | BeKindRewindAI | rvagent |
|--------|----------------|---------|
| **Framework** | smolagents (Python) + custom Python agents | Rust rlib + WASM |
| **Architecture** | 3 logical agents (Archivist/Worker/Scorer) via prompt isolation | 9 modular crates with typed agent graphs and subagent spawning |
| **Agent definition** | System prompts + tool decorators | Typed structs + middleware chain |
| **Context isolation** | Manual — separate function calls with isolated contexts | Built-in — subagent specs compile with isolated contexts |
| **Tool calling** | smolagents `ToolCallingAgent` with `@tool` decorators | Enum dispatch (`rvagent-tools`) with typed inputs |
| **Memory** | Dual: flat markdown + RuVector semantic | Built-in memory middleware in `rvagent-middleware` |
| **MCP** | None | Native `rvagent-mcp` crate with SSE transport |
| **Middleware** | None (manual implementation) | Chained: pipeline, todolist, filesystem, subagents, summarization, memory, skills, prompt caching, HITL, witness, tool sanitizer |
| **Human-in-loop** | Via scorer agent (scores below 7 = human consequence stated) | HITL middleware + witness middleware |
| **Orchestration model** | Sequential pipeline (capture→encode→transcribe→label→score→save) | Graph-based with subagent spawning, parallel execution possible |
| **Language** | Python | Rust + WASM |
| **Python bindings** | N/A (native Python) | None (no PyO3) — CLI subprocess or HTTP only |

### Key Architectural Differences

**BeKindRewindAI** uses a **sequential pipeline** driven by a single Archivist agent that:
1. Reads memory
2. Configures pipeline
3. Guides recording
4. Calls Worker (vocabulary, labeling) and Scorer (quality rating) as isolated function calls
5. Saves metadata

**rvagent** uses a **graph-based agent model** where:
- Agents are nodes with typed state and transitions
- Subagents can be spawned dynamically from specs
- Middleware chains add capabilities (memory, skills, HITL, tool sanitization)
- Tools are dispatched via enum pattern with typed inputs

## Python Bindings or CLI

**No Python bindings.** rvagent is a Rust-only framework:
- No PyO3/native Python extension
- Available as `rlib` (Rust library) or WASM
- Python access would require: subprocess CLI wrapper, HTTP calls to `rvagent-acp` server, or WASM via Pyodide

**CLI exists**: `rvagent` binary via `rvagent-cli` crate provides a terminal coding agent with TUI.

**MCP server mode**: `rvagent-mcp` exposes tools via Model Context Protocol (SSE transport), which could be consumed by any MCP client including Python code.

## Could rvagent Simplify or Enhance BeKindRewindAI?

### Where rvagent Could Help

1. **Replace smolagents dependency**: rvagent-core + rvagent-middleware could replace smolagents for agent orchestration, providing typed agent graphs instead of prompt-based agent definition

2. **Middleware infrastructure**: BeKindRewindAI currently has no middleware system. rvagent's middleware chain (skills, memory, HITL, tool sanitization) could replace manual implementations

3. **Subagent system**: Instead of manually calling `worker_generate_vocabulary()` and `scorer_rate_output()` as separate functions, rvagent's subagent system could formalize these as compiled specs with validation

4. **MCP integration**: rvagent-mcp could expose BeKindRewindAI's tools (detect_devices, start_capture, transcribe_video_file, etc.) via MCP protocol for external consumption

### Where rvagent Does NOT Help

1. **The pipeline is fundamentally different**: BeKindRewindAI's `pipeline.py` runs a **sequential media capture pipeline** (record→encode→validate→transcribe→dream→label→save). rvagent is not a media processing pipeline — it's an agent orchestration framework. rvagent cannot replace pipeline.py.

2. **Rust requirement**: BeKindRewindAI is Python. Adding rvagent would require either:
   - Running `rvagent-cli` as a subprocess
   - Running `rvagent-acp` as an HTTP server
   - WASM (impractical for desktop capture card access)

3. **Device/capture hardware access**: rvagent has no concept of VHS capture cards, FFmpeg recording, or media encoding — BeKindRewindAI's core value proposition

4. **Memory is already implemented**: BeKindRewindAI already has dual memory (markdown + RuVector via `harness.memory`)

### Verdict

**Low-to-medium relevance.** rvagent is a well-designed Rust agent framework but:

- It **cannot replace** `pipeline.py` (wrong problem domain — media processing vs. agent orchestration)
- It **cannot replace** smolagents without significant rework (rvagent is Rust, smolagents is Python)
- It **could** provide middleware infrastructure if BeKindRewindAI were rewritten in Rust or exposed via MCP
- The **subagent spec/validation system** is the most interesting feature for formalizing the Worker/Scorer isolation

If BeKindRewindAI ever migrates to a Rust-based architecture or exposes its tools via MCP, rvagent's middleware and subagent systems would be valuable. As a Python project with smolagents, the integration cost outweighs the benefits.

(End of file - total 108 lines)
