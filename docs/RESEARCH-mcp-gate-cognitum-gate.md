# Research: mcp-gate + cognitum-gate — AI Gateway

## What is Cognitum Gate?

Cognitum Gate is a real-time permission system for AI agents built as a `no_std` WASM kernel. It acts like a "smoke detector for AI agents" — continuously monitoring system coherence and deciding whether actions are safe to proceed, should be paused, or need human escalation. The gate provides formal safety guarantees through three stacked filters: structural (graph coherence via dynamic min-cut), shift (distribution change detection), and evidence (e-value accumulation for sequential hypothesis testing). Every decision outputs a signed witness receipt with a hash-chained audit trail. The key property is "anytime-valid" — you can stop computation at any time and still trust the decision.

## TileZero Acceleration

TileZero is the central arbiter in a distributed 256-tile WASM fabric. Each worker tile (1-255) maintains a local graph shard (~46KB) with connectivity tracking and evidence accumulation, while TileZero collects 64-byte reports from all tiles and issues Permit/Defer/Deny decisions with Ed25519-signed tokens. This distributed architecture allows the gate to scale across the fabric while maintaining coherence guarantees — TileZero merges worker reports into a supergraph, applies the three filters hierarchically, and coordinates permit token issuance.

## What is MCP?

MCP (Model Context Protocol) is the same protocol KiloCode uses for its tools. It standardizes how applications expose context and tools to LLMs, separating the concern of providing context from the actual LLM interaction. MCP has official SDKs for Python (modelcontextprotocol/python-sdk), JavaScript, and other languages.

## How mcp-gate Exposes RuVector as an MCP Tool

The mcp-gate crate is an MCP server implementation for the Cognitum Gate. It wraps the coherence gate functionality and exposes three MCP tools: `permit_action` (request permission for an action, returns decision + signed token), `get_receipt` (retrieve witness receipt for audit), and `replay_decision` (debug by replaying past decisions). Configuration is via environment variables (thresholds like `GATE_TAU_DENY`, `GATE_MIN_CUT`, signing key path) and it integrates with Claude-Flow as middleware. The mcp-gate server runs as a separate process and communicates via MCP protocol.

## Python SDK for MCP

Yes — the official Python SDK is at `modelcontextprotocol/python-sdk` (PyPI: `mcp`). It provides both a high-level `FastMCP` API for rapid server development and low-level APIs for full control. Install via `pip install mcp`. The SDK handles transport (stdio, SSE), protocol messages, and provides decorators for exposing tools, resources, and prompts. OpenAI's Agents SDK also has MCP support built-in.

## Relevance to BeKindRewindAI

The Cognitum Gate could formalize the existing 3-agent permission flow (Archivist → Worker → Dreamer), providing formal guarantees about when agents can act. However, it's designed for Rust/WASM deployment and would require significant integration work. The MCP exposure means RuVector tools could theoretically be called by any MCP-compatible AI system, including KiloCode — though the gate itself is a safety system, not a vector database.
