# Research: ruvector-tiny-dancer

## What is Tiny Dancer?

Tiny Dancer is a production-grade AI agent routing system that acts as a "smart traffic controller" for LLM requests. Instead of sending every query to an expensive, powerful model (like GPT-4), it quickly analyzes each request and decides whether to route to a fast/cheap model or a powerful/expensive one.

## FastGRNN Architecture

FastGRNN is a lightweight neural network architecture inspired by Microsoft Research. Key characteristics:
- **<1MB model size** with 80-90% sparsity (many weights are zero)
- **Sub-millisecond inference**: ~7.5µs per routing decision
- **INT8 quantization and magnitude pruning** for further size reduction
- Uses SIMD acceleration (simsimd) for 144ns feature extraction per candidate

## How Routing Works

1. Takes a query embedding + list of candidate responses
2. Extracts multi-signal features: semantic similarity, recency, frequency, success rate
3. Scores each candidate in microseconds via FastGRNN
4. High-confidence → lightweight model (fast & cheap)
5. Low-confidence → powerful model (accurate but expensive)

Example: Instead of sending 100 memory items to GPT-4, Tiny Dancer filters to top 3-5 in ~93µs total.

## Performance vs Full LLM

| Operation | Time |
|-----------|------|
| Feature extraction (per candidate) | 144-189ns |
| Model inference (per item) | 7.5µs |
| Complete routing (100 candidates) | ~93µs |

An LLM call typically takes 100ms-10s. Tiny Dancer is 1000x+ faster.

## mcporter API Access

The README does NOT mention mcporter integration. Available bindings:
- **Rust**: `ruvector-tiny-dancer-core` (crates.io)
- **Node.js**: `ruvector-tiny-dancer-node` (NAPI-RS)
- **WASM**: `ruvector-tiny-dancer-wasm`
- **Python**: NOT listed

Has an Admin API with HTTP endpoints for health checks, Prometheus metrics, hot model reloading.

## Could it Replace BeKindRewindAI Agents?

**Archivist** (vocabulary management, memory): YES — Tiny Dancer excels at ranking/filtering candidates by semantic similarity + recency. Could replace LLM-based vocabulary retrieval routing.

**Worker** (transcription, labeling): NO — Tiny Dancer doesn't generate content, only routes. Worker still needs LLM for actual transcription/labels.

**Dreamer** (creative generation): NO — routing decisions are the opposite of creative work. Dreamer needs full LLM capabilities.

## Verdict

Tiny Dancer is a **router, not a generator**. Best use case: filter vocabulary/memory candidates before sending to LLM. Could reduce Archivist's LLM calls by 70-85% for simple retrieval decisions. Not accessible via mcporter — would need WASM/Node.js bindings or custom Python wrapper.