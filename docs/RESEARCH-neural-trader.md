# Research: neural-trader crate

## 1. What Memory Replay Means Here

Memory replay in `neural-trader` is **NOT** traditional RL experience replay. It is a **selective, bounded replay system** for market microstructure events using a two-stage architecture:

**Stage A — Streaming Sketch** (cheap summaries, always hot):
- Count-Min sketch for repeated motifs
- Top-K for impactful levels, venues, regimes
- Rolling range sketches for volatility/imbalance bands
- Delta histograms for event transitions
- Purpose: detect recurring motifs, prioritize candidate writes, reduce storage pressure

**Stage B — Uncertainty-Guided Reservoir** (selective storage):
Stores high-value fragments when ANY condition holds:
1. High model uncertainty
2. Large realized PnL impact
3. Regime transition detected
4. Structural anomaly in graph
5. Rare queue pattern
6. High disagreement between prediction heads

Each segment stores: compact subgraph events, embedding snapshots, realized labels, coherence statistics, lineage metadata (model ID, policy version), and a witness hash for tamper detection.

**7 classification kinds:** `HighUncertainty`, `LargeImpact`, `RegimeTransition`, `StructuralAnomaly`, `RareQueuePattern`, `HeadDisagreement`, `Routine`

**Crate structure:**
| Crate | Purpose |
|-------|---------|
| `neural-trader-core` | Event types, graph schema, ingest traits |
| `neural-trader-coherence` | MinCut gate, CUSUM drift detection |
| `neural-trader-replay` | Reservoir store, witness receipts |
| `neural-trader-wasm` | Browser WASM bindings |

---

## 2. Coherence Mechanisms

The central mechanism is the **MinCut Coherence Gate**, which computes a compact induced subgraph linking incoming market events, local price levels, relevant prior memories, current strategy state, and risk nodes. From this it derives: canonical mincut partition, cut value, boundary node identities, cut drift over time, embedding drift by partition, and CUSUM alarms.

**Tiered gate permissions:**

| Operation | Requirement |
|-----------|-------------|
| `allow_retrieve` | MinCut >= regime floor only |
| `allow_write` | MinCut + CUSUM + drift + boundary stable |
| `allow_learn` | All above + drift < 50% of max |
| `allow_act` | All above (full gate) |

**Regime-adaptive thresholds:**

| Regime | MinCut Floor |
|--------|-------------|
| Calm | 12 |
| Normal | 9 |
| Volatile | 6 |

**CUSUM Drift Detection:** Blocks mutations when drift score exceeds threshold (default 4.5).

**Proof-Gated Mutation Protocol:**
```
Compute features → Coherence gate → Policy kernel → Mint token → Apply mutation → Append receipt
```

---

## 3. Benchmarks vs Baseline

**No numerical benchmarks found.** The ADR-085 outlines planned metrics but none are published:

**Planned core metrics:**
- **Prediction:** Fill probability calibration, short-horizon direction AUC, slippage error, realized adverse selection
- **Trading:** PnL, Sharpe/information ratio, max drawdown, inventory risk, cancel-to-fill quality, venue quality
- **Coherence:** Average mincut by regime, partition stability, drift detection precision, false-positive gate rate, rollback trigger quality
- **Systems:** p50/p95/p99 latency, retrieval latency, write amplification, storage growth, witness overhead

**Acceptance criteria (no empirical results yet):**
- Phase 1: Replayable end-to-end pipeline, measurable improvement over price-only baseline
- Phase 2: Stable gate behavior under live feed noise, no uncontrolled action bursts
- Phase 3: Strict exposure limits enforced, slippage within approved band

---

## 4. Python Bindings

**No Python/PyO3 bindings exist.**

| Type | Package | Access |
|------|---------|--------|
| WASM | `@ruvector/neural-trader-wasm` (npm) | Browser, Node.js 22+ |
| Node.js NAPI | `nt-napi-bindings` (crates.io) | Native Node.js FFI |
| Rust | Direct crate usage | Native only |

---

## 5. Applicability to BeKindRewindAI Memory Loop

**Low direct applicability, but architecture patterns are transferable.**

**Domain mismatch:** `neural-trader` is designed for market microstructure (order books, trades, price levels). Whisper uses CTC-based transcription, not transformer attention — different paradigm.

**What could transfer:**
- Two-tier selective memory (streaming sketch + uncertainty-guided reservoir) — similar to how BeKindRewindAI could prioritize which recordings to replay
- Coherence gating for memory admission — could filter which historical transcriptions are reliable
- Witness receipts + proof-gated mutation — excellent fit for audit trail in transcription accuracy tracking
- Bounded reservoir with O(1) eviction — relevant for managing a rolling buffer of past recordings

**What would NOT help:**
- MinCut coherence on market graph — no order book or price level data in speech transcription
- CUSUM drift detection on market parameters — irrelevant for transcription quality tracking
- Regime detection for trading — irrelevant

**Verdict:** The *architecture* (selective replay with uncertainty guidance, bounded reservoir, coherence-gated admission, audit receipts) is conceptually applicable to any memory loop that replays past data for improved accuracy. But the specific implementation is market-domain and would need significant reimplementation for speech/transcription use cases. No Python bindings means direct integration is not feasible without a PyO3 wrapper.