# Research: ruvector-delta-core (Verified from docs.rs)

**Source**: [crates.io](https://crates.io/crates/ruvector-delta-core) | [docs.rs](https://docs.rs/ruvector-delta-core/0.1.0/ruvector_delta_core/) | [GitHub](https://github.com/ruvnet/ruvector)

**Note**: The crate source was not present in the workspace. Research verified against official docs.rs documentation.

## 1. What "Delta" Means

**Vector delta** — the difference between two f32 embedding vectors. Analogous to a diff/patch for binary data. NOT delta indexing, delta graphs, or temporal graphs.

Core concept: "vector versioning" — compute change from V1 to V2, store only the change (sparsely), replay to reconstruct any state.

## 2. Temporal Data Handling

**DeltaStream** provides event-sourced temporal ordering:
- Every delta entry gets a `timestamp_ns: u64` (nanoseconds since epoch)
- `get_time_range(start_ns, end_ns)` — retrieve deltas in any time window
- `replay_to_sequence(initial, target_sequence)` — reconstruct state at specific sequence
- `create_checkpoint(value)` — snapshot full base state; later replay from that checkpoint
- Automatic compaction via delta composition when stream exceeds limits

**DeltaWindow** provides time-bounded aggregation:
- Window types: Tumbling (non-overlapping), Sliding (overlapping), Count-based
- `WindowResult` emits: `start_ns`, `end_ns`, `count`, composed `delta`
- Aggregators: `SumAggregator`, `AverageAggregator`, `EmaAggregator`

**BeKindRewindAI relevance**: VHS tapes arrive sequentially over real time. Each tape's vocabulary embedding update produces a delta. Query "what did vocabulary look like after tape 7?" or "what changed between 2pm and 4pm?"

## 3. Key Data Structures and Algorithms

### Core Delta Trait
```rust
pub trait Delta: Sized + Send + Sync + Clone {
    type Base;        // Vec<f32> for VectorDelta
    type Error;        // DeltaError
    
    fn compute(old: &Self::Base, new: &Self::Base) -> Self;
    fn apply(&self, base: &mut Self::Base) -> Result<(), Self::Error>;
    fn compose(self, other: Self) -> Self;  // this.then(other)
    fn inverse(&self) -> Self;
    fn is_identity(&self) -> bool;
    fn byte_size(&self) -> usize;
}
```

### VectorDelta
```rust
pub struct VectorDelta {
    pub value: DeltaValue<f32>,      // Identity | Sparse | Dense | Replace
    pub dimensions: usize,
    pub sparsity_threshold: f32,      // default 0.7
}
```

Delta computation: `new[i] - old[i]` with epsilon filtering for near-zero changes. Sparsity auto-detected: if `1 - (nonzero_dims / total_dims) > 0.7`, use sparse storage.

### Encoding Layer
Four strategies with `HybridEncoding` auto-selection:
- **Dense**: all f32 values (when >30% indices modified)
- **Sparse**: `(index, value)` pairs (when <30% modified)
- **RunLength**: `(value, count)` runs
- **Hybrid**: auto-selects per-delta

### Compression Layer
Stacked on encoding: None, LZ4, Zstd, DeltaOfDelta, Quantized (f32→f16). Custom header with magic bytes `0x44454C54 = "DELT"`.

## 4. BeKindRewindAI Memory Loop

**High relevance** for temporal memory storage:

1. **VHS tape versioning**: Each processed tape updates vocabulary. Store `VectorDelta` between states. Replay from checkpoint to get "vocabulary at tape N."

2. **Temporal queries**: `DeltaStream::get_time_range()` for "what changed during Q4 2025?"

3. **Memory compression**: Store deltas (sparse) instead of full snapshots. Delta-of-delta + quantization further reduce storage.

4. **Window summarization**: `DeltaWindow::tumbling(size_ns)` aggregates changes within time windows into composed deltas — daily/weekly vocabulary evolution summaries.

5. **Scrubbing/replay**: `create_checkpoint()` after each tape. User can "go back to state after tape 12."

## 5. API Surface — Python Access

**Pure Rust library — no Python bindings provided.**

Available integration paths:
1. **WASM compilation** — could compile to WASM, no bindings provided
2. **Rust binary with IPC** — wrap in server process, HTTP/stdin communication
3. **Reimplement in Python** — algorithms are straightforward

**Exposed API** (Rust):
```rust
// Core types
DeltaStream<VectorDelta>, DeltaWindow<VectorDelta>
VectorDelta::compute(&old, &new) -> Self
delta.apply(&mut base)
stream.push_with_timestamp(delta, timestamp_ns)
stream.get_time_range(start_ns, end_ns) -> Vec<&Delta>
stream.replay(initial) -> Result<Base>
stream.create_checkpoint(value)
window.tumbling(size_ns) // create tumbling window
```

**Feature flags**: `std` (default), `simd`, `serde`, `compression`

**Dependencies**: `thiserror`, `bincode`, `smallvec`, `parking_lot`, `arrayvec`. Optional: `simsimd`, `lz4_flex`, `zstd`.

## Summary

ruvector-delta-core is a **vector delta/diff library** with **event-sourced streaming** and **time-window aggregation**. Computes sparse/dense diffs between f32 vectors, composes/inverts them, streams with nanosecond timestamps and checkpoints, compresses results. For BeKindRewindAI: powers a versioned vocabulary store where each VHS tape produces a delta — enabling temporal queries on memory state. Requires Rust/WASM integration work to use from Python.
