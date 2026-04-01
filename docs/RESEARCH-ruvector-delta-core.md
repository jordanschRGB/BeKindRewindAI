# Research: ruvector-delta-core

## What "Delta" Means Here

"Delta" in this crate is **vector delta** — the difference between two f32 embedding vectors, analogous to a diff/patch for binary data. It is NOT delta indexing, delta graphs, or temporal graphs. Think "vector versioning" or "embedding diffing": compute the change from V1 to V2, store only the change (sparsely), replay it to reconstruct any state.

## Temporal Data Handling

The temporal layer sits on top of the delta concept via two mechanisms:

**DeltaStream** (`stream.rs`):
- Every delta entry gets a `timestamp_ns: u64` (nanoseconds since epoch)
- `get_time_range(start_ns, end_ns)` retrieves deltas in any time window
- `replay_to_sequence(initial, target_sequence)` reconstructs state at a specific sequence
- `create_checkpoint(value)` snapshots the full base state at a point — later replay from that checkpoint
- Automatic compaction via delta composition when stream exceeds `max_deltas` or `max_memory_bytes`

**DeltaWindow** (`window.rs`):
- Time-bounded aggregation of deltas into composed "window deltas"
- Window types: Tumbling (non-overlapping), Sliding (overlapping), Session (gap-based), Count-based
- Emits `WindowResult` with `start_ns`, `end_ns`, `count`, and composed `delta`
- Aggregators: `SumAggregator` (compose all), `AverageAggregator` (scale by 1/count), `EmaAggregator` (exponential moving average)

This is directly relevant to BeKindRewindAI: VHS tapes arrive sequentially over real time. Each tape's vocabulary embedding update produces a delta. You can replay "what did the vocabulary look like after processing tape 7?" or query "what changed between 2pm and 4pm?"

## Key Data Structures and Algorithms

### Core Delta Types (`delta.rs`)

```
Delta trait: compute(old, new) -> Self, apply(delta, base), compose(d1, d2), inverse()

DeltaValue<T>: Identity | Sparse(SmallVec<[DeltaOp<T>; 8]>) | Dense(Vec<T>) | Replace(Vec<T>)

VectorDelta: { value: DeltaValue<f32>, dimensions: usize, sparsity_threshold: f32 }
```

The sparsity threshold is hardcoded at 0.7 — if `1 - (nonzero_dims / total_dims) > 0.7`, use sparse storage (only store the changed indices). Otherwise use dense.

Key algorithms:
- **Delta computation**: `new[i] - old[i]` with epsilon=1e-7 to filter near-zero changes
- **Delta composition**: Merges two deltas by adding their value changes at each index (sparse via BTreeMap, dense via element-wise addition)
- **Delta inverse**: Negates all values (cannot invert `Replace` variants)
- **L2/L1 norms**: Computed from sparse ops or dense arrays

`SparseDelta` is an alternative that stores `(index, old_value, new_value)` triples instead of just the delta. Useful when you need the original values too.

### Encoding Layer (`encoding.rs`)

Four encoding strategies with a `HybridEncoding` that auto-selects:

| Encoding | Storage | Best For |
|----------|---------|----------|
| Dense | All f32 values | Dense changes (>30% indices modified) |
| Sparse | `(index, value)` pairs | Sparse changes (<30% modified) |
| RunLength | `(value, count)` runs | Consecutive identical values |
| Hybrid | Auto-selects | Default — picks best per-delta |

### Compression Layer (`compression.rs`)

Delta-specific compression stacked on top of encoding:

| Codec | Approach |
|-------|---------|
| None | Raw encoded bytes |
| LZ4 | `lz4_flex` (feature-gated) |
| Zstd | `zstd` (feature-gated) |
| DeltaOfDelta | `v[i] - v[i-1]` then `v[i] - v[i-1] - (v[i-1]-v[i-2])` — good for sequential data |
| Quantized | f32 → f16 bit representation |

Custom `CompressedHeader` with magic bytes (`0x44454C54 = "DELT"`), FNV-1a checksum.

### Stream and Window (`stream.rs`, `window.rs`)

- `DeltaStream<D>`: `VecDeque<StreamEntry<D>>` with `checkpoint_sequence` tracking. Compaction composes consecutive deltas. Memory-tracked with `byte_size()` on each delta.
- `DeltaWindow<D>`: `VecDeque<WindowEntry<D>>` with `window_start_ns`. Tumbling emits and advances by full `size`; Sliding emits then advances by `slide` (smaller than size).

## BeKindRewindAI Memory Loop Relevance

**High relevance** for storing and retrieving memories with temporal ordering:

1. **VHS tape versioning**: Each processed tape updates the vocabulary embedding. Store `VectorDelta` between consecutive states. Replay from any tape checkpoint to get "vocabulary at tape N."

2. **Temporal queries**: "What vocabulary terms changed during Q4 2025?" — `DeltaStream::get_time_range()` on the tape processing deltas.

3. **Memory compression**: Rather than storing full vocabulary snapshots, store only deltas (sparse). The compression layer (delta-of-delta, quantization) further reduces storage.

4. **Window-based summarization**: `DeltaWindow::tumbling(size_ns)` to aggregate all changes within a time window into a single composed delta — useful for daily/weekly summary views of how the vocabulary evolved.

5. **Scrubbing/replay**: `create_checkpoint()` after each tape. If user wants to "go back to how the system was after tape 12", replay from that checkpoint.

The session window type (`Session`) with gap-based closing is particularly interesting: if processing stops for a long gap, it closes the window — useful for detecting "context switches" in the archival process.

## API Surface — How Would Python Call This?

**Not directly accessible from Python.** No PyO3, no mcporter, no WASM bindings, no server binary in this crate. It is a pure Rust library.

Options for Python integration:
1. **WASM compilation** — This crate could be compiled to WASM, but no bindings are provided
2. **Rust binary with IPC** — Wrap in a small Rust server process, communicate via stdin/stdout or HTTP
3. **Rewrite in Python** — The algorithms are straightforward enough to reimplement

**Dependency footprint**: `thiserror`, `bincode`, `smallvec`, `parking_lot`, `arrayvec`. Optional: `simsimd` (SIMD), `lz4_flex`, `zstd` (compression), `serde`.

**Feature flags**: `std` (default), `simd`, `serde`, `compression`

## Summary

ruvector-delta-core is a **vector delta/diff library** with **event-sourced streaming** and **time-window aggregation**. It computes sparse/dense diffs between f32 vectors, composes/inverts them, streams with nanosecond timestamps and checkpoints, and compresses the result. For BeKindRewindAI, it could power a versioned vocabulary store where each VHS tape's processing produces a delta — enabling true temporal queries on memory state. But it requires Rust/WASM integration work to expose to Python.
