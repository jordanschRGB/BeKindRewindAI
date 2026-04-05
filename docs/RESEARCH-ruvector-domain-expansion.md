# Research: ruvector-domain-expansion — Transfer Learning

## What is Domain Expansion?

Domain expansion is a **cross-domain transfer learning framework** that enables knowledge learned in one domain to automatically improve performance in a different domain. Unlike traditional fine-tuning which trains one task at a time, domain expansion extracts compact "priors" (Beta posteriors from Thompson Sampling) from a trained domain and seeds them into target domains.

## How It Bootstraps from Past Learning

1. **Train on Domain 1** (e.g., Rust synthesis) → produces TransferPrior (posterior summaries)
2. **Extract priors** — NOT raw trajectories, but compact Beta posteriors per context bucket/arm
3. **Seed Domain 2** with dampened priors from Domain 1
4. **Verify transfer** — measures acceleration (cycles to convergence with vs without transfer)
5. **Generalization rule**: a delta is promotable only if it improves Domain 2 **without regressing Domain 1**

The engine uses **Meta Thompson Sampling** to pick the best strategy per context, **Population-Based Search** (8 policy kernel variants evolve in parallel), and **Curiosity-Driven Exploration** (UCB-style bonus for under-visited contexts).

## Practical Use Cases

- Genomics → Molecular Design (sparse biological feature vectors transfer)
- Trading → Resource Allocation (risk/reward models apply to budget optimization)
- Quantum → Signal Processing (noise detection patterns transfer)
- Rust Synthesis → Structured Planning (code compilation and planning share sequential reasoning)
- Scientific OCR → Planning (equation structure seeds logical step decomposition)

## mcporter API Accessibility

**No direct mcporter API** for domain-expansion. The crate is available as:
- **Rust library** (`ruvector-domain-expansion` on crates.io)
- **WASM bindings** (`ruvector-domain-expansion-wasm`) for JavaScript
- **RVF packaging** (`rvf` feature flag) — serialize trained engines as `.rvf` cognitive containers
- **ruvector-cli** exposes some RuVector features via MCP server, but domain-expansion specifically is not documented as an MCP tool

The closest MCP integration is `@ruvector/rvf-mcp-server` for RVF vector database operations, not the domain expansion transfer learning specifically.

## Relevance to BeKindRewindAI Memory/Vocabulary Learning Loop

**Highly relevant** — domain expansion formalizes exactly what BeKindRewindAI needs:

1. **Learning from one tape, applying to the next** — extract vocabulary priors from processed tapes, seed recognition on new tapes
2. **Transfer verification** — ensures new vocabulary learning doesn't regress previously learned terms (EWC++ protection)
3. **Acceleration measurement** — proves vocabulary recognition gets faster with each tape
4. **Thompson Sampling** for strategy selection could optimize which labeling approach works best per tape type

However, domain-expansion is a **Rust/WASM library**, not Python-accessible. Integration would require either:
- Python FFI bindings to the Rust crate
- Running domain-expansion as a separate service with HTTP/gRPC API
- Using the WASM bindings directly in Python (if supported)

The **sona crate** (MicroLoRA <1ms adaptation) mentioned in the ecosystem is specifically designed for live adaptation without forgetting — potentially more practical for BeKindRewindAI's incremental learning needs.
