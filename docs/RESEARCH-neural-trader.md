# Research: neural-trader (coherence + replay for memory loops)

**Bead:** `95dcdbde-0f6b-4072-ad16-db9350964a5d`
**Crates examined:** `neural-trader-core`, `neural-trader-coherence`, `neural-trader-replay`, `neural-trader-wasm`
**Source:** RuVector GitHub (`ruvnet/RuVector`), ADR-085, ADR-086

---

## 1. What does this crate do — what's a "neural trader" in this context?

**Short answer: A coherence-gated market microstructure system that uses dynamic graph partitioning (MinCut) to decide when to trust, remember, and act on market events.**

"Neural trader" in this context has **nothing to do with financial trading**. The name is inherited from a separate JavaScript trading library in the RuVector examples. The RuVector neural-trader crates (`neural-trader-core`, `neural-trader-coherence`, `neural-trader-replay`) are a **market microstructure research platform** — they model limit order books as typed heterogeneous graphs, embed them into vectors, and use MinCut graph partitioning as a first-class coherence signal.

The core idea (ADR-085): treat market data as a living graph (order queues, price levels, trades, venues, participants, regimes) rather than a time series of candles. Then:

- **Ingest** raw market events (trades, cancels, modifies, book snapshots) into typed graph state
- **Embed** subgraph windows into vectors (book state, queue state, event stream, regime)
- **Gate** every operation (retrieve, write, learn, act) through a MinCut coherence decision
- **Replay** high-value fragments with full witness receipts for auditability

The crates implement **only the foundation layers** — event schema, coherence gate traits+implementations, and replay segment storage. The full GNN/temporal-attention learning stack is planned but not yet implemented (per ADR-085's implementation plan).

---

## 2. How does replay work — is this like episodic memory replay in neuroscience?

**Partially similar to neuroscience replay, but with a different selection mechanism.**

In neuroscience (hippocampal replay), experiences are re-activated during rest/sleep to consolidate memories and detect patterns. The key features are:
- Content-addressable retrieval by similarity
- Temporal sequencing (place cells fire in order)
- Both sharp-wave ripples (awake) and slow oscillations (sleep) replay

RuVector's `neural-trader-replay` crate works similarly in concept but differently in mechanics:

**What it does:**
- `ReplaySegment` — a sealed, signed memory fragment containing: events, embedding snapshot, labels (realized outcomes), coherence stats at write time, lineage metadata, and a witness hash
- `SegmentKind` discriminants: `HighUncertainty`, `LargeImpact`, `RegimeTransition`, `StructuralAnomaly`, `RareQueuePattern`, `HeadDisagreement`, `Routine`
- `ReservoirStore` — bounded O(1) eviction reservoir using `VecDeque`; writes only accepted when the coherence gate `allow_write == true`
- Two-stage memory design (ADR-085): **Stage A** (streaming sketch with Count-Min, Top-K) → **Stage B** (uncertainty-guided reservoir selection)

**Key differences from neuroscience:**
- Selection is **driven by coherence gate scores**, not by temporal contiguity or reward signals
- No sequencing or ordering — purely set-based retrieval by symbol + limit
- The `ReservoirStore::retrieve()` is a simple filter-by-symbol + take-N, not similarity search
- No Hebbian/synaptic consolidation — just bounded storage with FIFO eviction

**Similarity to neuroscience replay:**
- Uncertainty-guided selection (high model uncertainty → store it) mirrors "novelty signals" in hippocampal encoding
- Regime transition detection mirrors pattern separation in dentate gyrus
- Bounded reservoir with O(1) eviction mirrors constraints on memory capacity

---

## 3. How does coherence scoring work — is it different from prime-radiant's coherence?

**Yes, fundamentally different from prime-radiant's coherence. They share the word but not the mechanism.**

| Aspect | prime-radiant coherence | neural-trader coherence |
|--------|------------------------|------------------------|
| **Mechanism** | Belief graph + coherence energy + compute ladder (gradient-based energy minimization) | MinCut graph partitioning on a market microstructure graph |
| **Input** | LLM hidden states, activations, attention patterns | Order book graph: price levels, queues, trades, participants |
| **Output** | Per-token coherence score, hallucinations flagged | Four boolean gates (retrieve/write/learn/act) + mincut value + CUSUM drift score |
| **Domain** | Text generation, hallucination detection | Market microstructure, limit order book stability |
| **Gate decisions** | Implicit (energy-based) | Explicit: `allow_retrieve`, `allow_write`, `allow_learn`, `allow_act` |

**neural-trader coherence specifically:**
1. **MinCut floor** — regime-dependent threshold (Calm=12, Normal=9, Volatile=6). The market graph must have a sufficiently coherent partition before any operation is allowed.
2. **CUSUM drift detection** — cumulative sum tracker for regime instability (threshold 4.5). Tracks structural breaks in the order book.
3. **Embedding drift score** — magnitude of embedding change since last stable window (max 0.5, learning requires <0.25)
4. **Boundary stability** — requires 8 consecutive windows with stable partition identity before allowing writes/acts

The `ThresholdGate::evaluate()` returns a `CoherenceDecision` with four boolean permissions. **Retrieval is most permissive** (only needs cut_ok), **learning is strictest** (needs base_ok + half drift margin).

---

## 4. How would this apply to BeKindRewindAI's memory loop — replaying VHS memories to detect patterns over time?

**Conceptually applicable, but would require significant adaptation. The coherence-gated reservoir pattern maps well to VHS memory replay, but the market-specific graph schema doesn't.**

**How it maps:**

| neural-trader concept | VHS memory equivalent | Feasibility |
|-----------------------|----------------------|-------------|
| `MarketEvent` | VHS frame / transcript segment with timestamp | Direct mapping possible |
| `Symbol` in graph | A specific VHS tape title or show | Direct |
| `Venue` | Capture card source / time slot | Direct |
| `PriceLevel` | Frame embedding cluster | Reinterpret |
| `RegimeLabel` (Calm/Normal/Volatile) | Low/medium/high vocabulary change regime | Highly relevant |
| `MinCut` partition stability | Structural coherence of scene transitions | Analogous |
| `CUSUM drift` | Sudden genre/theme shifts between tapes | Analogous |
| `ReservoirStore` | Bounded memory of VHS replay segments | Directly applicable |
| `ReplaySegment` with `SegmentKind` | Replay fragment tagged: `SceneRepeat`, `ThemeDrift`, `LowConfidence`, `RareVocab` | Reasonable extension |
| `CoherenceDecision` gating write/retrieve | Decide whether to remember / retrieve this replay | Directly applicable |
| `WitnessReceipt` audit log | Full chain of custody for each memory write | Directly applicable |

**What BeKindRewindAI would gain:**
1. **Structured memory admission** — not all VHS frames stored, only those passing a coherence gate (stable scene, regime transition, high vocabulary surprise)
2. **Bounded memory** — `ReservoirStore` with O(1) eviction prevents unbounded VHS memory growth
3. **Drift detection** — CUSUM tracks vocabulary/theme instability across tapes, useful for "this tape is very different from usual"
4. **Tiered permissions** — retrieval always available, learning gated tighter (prevents learning from noisy/unstable transcriptions)
5. **Audit trail** — `WitnessReceipt` for every memory write enables "why did we remember this?" forensics

**What doesn't map:**
- Market microstructure concepts (order books, queue length, fill hazard, cancel hazard) have no VHS equivalent
- The `MarketEvent` schema is specific to exchanges (venue, side, price_fp, qty_fp)
- No temporal ordering or sequencing in `ReservoirStore::retrieve()` — VHS scenes have narrative order that matters

**Practical path for BeKindRewindAI:**
A `VHSMemoryStore` could use the same `ReservoirStore` + `CoherenceGate` pattern, with:
- `SegmentKind`: `SceneRepeat`, `VocabSurprise`, `ThemeShift`, `LowConfidence`, `CommercialBreak`, `Routine`
- `GateContext` driven by vocabulary embedding drift + VHS structural stability (scene cut frequency, audio silence gaps)
- No need for the market graph types (`NodeKind`, `EdgeKind`)

---

## 5. What's the API surface for Python?

**No native Python/PyO3 bindings exist. Only WASM bindings via `@ruvector/neural-trader-wasm`.**

**Available access patterns:**

### NPM/WASM (browser/Node.js)
Published package: `@ruvector/neural-trader-wasm` (v0.1.1)
```javascript
import init, { ReservoirStoreWasm, ThresholdGateWasm, GateConfigWasm, GateContextWasm, CoherenceDecisionWasm } from '@ruvector/neural-trader-wasm';

await init();
const store = new ReservoirStoreWasm(1000);
const gate = new ThresholdGateWasm(new GateConfigWasm());
```

Exported WASM types:
- `MarketEventWasm` — event creation and field access
- `GraphDeltaWasm` — graph change notifications  
- `ThresholdGateWasm` — coherence gate evaluation
- `GateConfigWasm` — configurable thresholds
- `GateContextWasm` — gate input context
- `CoherenceDecisionWasm` — four boolean permissions + scores
- `ReservoirStoreWasm` — bounded replay memory
- `ReplaySegmentWasm` — memory fragment serialization
- `version()`, `healthCheck()`

### CLI subprocess
No standalone CLI binary is published. RuVector's `ruvector-cli` does not include neural-trader subcommands.

### HTTP/REST
No HTTP API for neural-trader crates. The full `ruvector-server` (Axum REST API) wraps `ruvector-core` HNSW operations, not neural-trader.

### What would be needed for Python
To use this from Python today:
1. **WASM via Pyodide** — load `@ruvector/neural-trader-wasm` in a browser/JS runtime, call from Python via Pyodide
2. **CLI wrapper** — spawn `ruvector-cli` subprocess (doesn't exist for neural-trader)
3. **Custom PyO3 bindings** — write Rust bindings wrapping `neural-trader-core` + `neural-trader-coherence` + `neural-trader-replay` using `pyo3`, build and publish to PyPI
4. **REST sidecar** — wrap neural-trader in an Axum HTTP server (currently not implemented), call from Python with `requests`

**Honest assessment:** The neural-trader crates are early-stage (v0.1.0, "Proposed" ADR), have no Python bindings, no published binaries, and no REST API. They are research scaffolding, not a usable Python library. The `neural-trader-wasm` npm package is the only published artifact.

---

## Verdict for BeKindRewindAI

**Relevance: Medium-High for concepts, Low for implementation.**

The **coherence-gated reservoir pattern** (bounded memory + drift detection + tiered learn/retrieve/write permissions) is directly applicable to VHS memory replay and would reinforce the "memory improves over time" promise. However:

1. The neural-trader crates are **market-microstructure specific** — the graph schema (order books, venues, price levels) doesn't map to VHS
2. The crates are **early-stage research** (v0.1.0, only traits + simple implementations exist)
3. **No Python bindings** — only WASM/npm, which doesn't help BeKindRewindAI (Python app with local hardware access)
4. The **ReplaySegment + ReservoirStore + ThresholdGate** pattern could be reimplemented generically for VHS without the market graph types

**Recommendation:** Use the neural-trader as a **design reference** for the memory subsystem, not as a dependency. Implement a `VHSMemoryStore` with the same coherence-gated reservoir pattern, using vocabulary embedding drift instead of MinCut partitioning.
