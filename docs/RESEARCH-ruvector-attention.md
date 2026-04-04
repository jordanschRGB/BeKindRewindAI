# Research: ruvector-attention

**Bead**: 6fe25ae4-73a2-4bc4-92af-627fa33f1570
**Crate**: `ruvector-attention` (with `ruvector-attention-wasm`)
**Repository**: https://github.com/ruvnet/ruvector
**crates.io**: https://crates.io/crates/ruvector-attention
**npm**: https://registry.npmjs.org/ruvector-attention-wasm (v2.1.0)

---

## 1. What Attention Mechanisms It Implements

`ruvector-attention` implements **46 attention mechanisms** grounded in 7 mathematical theories:

### Standard Attention
- Scaled Dot-Product: `softmax(QK^T / √d)V`
- Multi-Head: Parallel attention heads with diverse representations

### Sparse Attention (Memory Efficient)
- **Flash Attention**: O(n) memory complexity with tiled computation
- **Linear Attention**: O(n) complexity using kernel approximation (Performer-style)
- **Local-Global**: Sliding window + global tokens (Longformer-style)

### Geometric Attention
- **Hyperbolic Attention**: Attention in hyperbolic space for hierarchical data
- **Mixed Curvature**: Dynamic curvature combining Euclidean + Hyperbolic + Spherical

### Graph Attention
- Edge-Featured GAT
- RoPE (Rotary Position Embeddings for graphs)

### Mixture-of-Experts
- MoE Attention with top-k routing
- Expert capacity mechanisms

### 7 Mathematical Theories
1. **Optimal Transport**: Sliced Wasserstein, Centroid OT
2. **Mixed Curvature**: Tangent space mapping, fused E+H+S kernel
3. **Topology**: Coherence-based 3-mode switching (Stable/Cautious/Freeze)
4. **Information Geometry**: Fisher metric, natural gradient
5. **Information Bottleneck**: KL divergence compression (VIB)
6. **PDE/Diffusion**: Heat equation on similarity graph
7. **Unified Diagnostics**: Health monitoring + automatic mode selection

---

## 2. WASM Support and Browser Compatibility

**Yes, full WASM support.**

### Crates
- `ruvector-attention-wasm` (v2.1.0): WebAssembly bindings
- `ruvector-attention-node` (v2.0.4): Node.js bindings

### Installation
```bash
npm install ruvector-attention-wasm  # Node.js / bundlers
```

### Browser Support
The WASM module targets modern browsers with:
- ES modules (`type: "module"`)
- Full TypeScript definitions included
- Targets: `x86_64-unknown-linux-gnu`, `aarch64-apple-darwin`, `x86_64-pc-windows-msvc`, `i686-pc-windows-msvc`

### Key Features
- GPU acceleration via wgpu WGSL shaders (vec4 optimized)
- SIMD fallback: AVX-512 / AVX2 / NEON
- Zero-copy data transfer where possible
- Built with `opt-level = "s"` and LTO

### API (WASM)
```typescript
import { initialize, MultiHeadAttention, HyperbolicAttention, FlashAttention, MoEAttention } from 'ruvector-attention-wasm';

await initialize();

const attention = new MultiHeadAttention({ dim: 64, numHeads: 8 });
const output = attention.compute(query, keys, values);

// CGT Sheaf Attention (Prime-Radiant integration)
import { CGTSheafAttention } from 'ruvector-attention-wasm';
const cgt = new CGTSheafAttention({ dim: 128, numHeads: 8, coherenceThreshold: 0.3 });
const result = cgt.compute(query, keys, values);
```

---

## 3. Benchmarks vs Vanilla Softmax Attention

### From RuVector Benchmarking Guide

| Benchmark | Result |
|-----------|--------|
| Flash Attention | 2.3x faster, 5x less memory than standard |
| Linear Attention | O(n) scaling for sequences >4096 |
| Local-Global (w=256) | 60% of standard attention cost |
| Sliced Wasserstein | 1.8x slower than standard (but better distribution matching) |
| Mixed Curvature | ~1.3x standard with tangent space optimization |
| Diffusion Attention | 2-10x slower (depending on steps), captures multi-scale structure |

### Performance Targets (from benchmarking guide)
- **10K vectors**: p50 < 100µs, p95 < 200µs, QPS 10,000+
- **100K vectors**: p50 < 500µs, p95 < 1ms, QPS 2,000+
- **1M vectors**: p50 < 1ms, p95 < 2ms, QPS 1,000+

### Complexity Comparison
| Mechanism | Time | Memory | Use Case |
|-----------|------|--------|----------|
| Scaled Dot-Product | O(n²) | O(n²) | Short sequences |
| Flash Attention | O(n²) | O(n) | Long sequences |
| Linear Attention | O(n) | O(n) | Very long sequences |
| Local-Global | O(n·w) | O(n·w) | Document processing |

### Architecture Modules
```
ruvector-attention/
├── src/
│   ├── attention/           # Standard: scaled_dot_product, multi_head
│   ├── sparse/              # Flash, linear, local_global
│   ├── graph/               # Edge-featured GAT, RoPE
│   ├── hyperbolic/          # Hyperbolic attention, mixed_curvature
│   ├── moe/                 # Expert modules, router, moe_attention
│   ├── transport/           # Sliced Wasserstein, centroid OT
│   ├── curvature/           # Tangent space, fused attention, quantization
│   ├── topology/            # Coherence, policy, gated_attention
│   ├── info_geometry/       # Fisher metric, natural gradient
│   ├── info_bottleneck/     # KL divergence, VIB bottleneck
│   ├── pde_attention/       # Laplacian, diffusion
│   ├── unified_report/      # Geometry report, recommendations
│   └── sdk/                 # Builder API, pipeline, presets (BERT, GPT, Longformer, etc.)
```

---

## 4. Python Bindings or CLI Access

### Python Bindings
**No direct PyO3 bindings** for `ruvector-attention`. Python access via:
1. **WASM through browser**: Load in Pyodide/WebAssembly
2. **npm package**: Use through Node.js/Python FFI

### CLI Access
No standalone CLI binary published. CLI access through:
- `ruvllm-cli` subprocess wrapper (from related ruvllm crate)
- REST API via ruvector-server (separate crate)

### NPM Packages Available
| Package | Version | Purpose |
|---------|---------|---------|
| `ruvector-attention-wasm` | 2.1.0 | WASM bindings (Node.js + browsers) |
| `ruvector-attention-node` | 2.0.4 | Node.js native bindings |
| `ruvector-attention-unified-wasm` | 0.1.0 | Unified bindings for 18+ mechanisms |

---

## 5. Would This Improve BeKindRewindAI?

### Transcriber Improvement: **Unlikely Direct Benefit**
- BeKindRewindAI uses Whisper for transcription, which is a CTC-based model that doesn't use attention mechanisms in the same way as transformers
- Flash Attention and other mechanisms target transformer architectures, not RNN/CTC models
- If the transcriber used a transformer-based model (e.g., Conformer), then Flash Attention would reduce memory for long audio sequences

### Encoder Quality: **Possibly Indirect**
- If the encoder uses attention for vocabulary/memory lookups, the multi-head attention or graph attention could help
- The hyperbolic attention is designed for hierarchical data — if vocabulary has hierarchical structure, this could help

### More Relevant Mechanisms for BeKindRewindAI
1. **Flash Attention**: Would only help if processing long transcripts with transformers
2. **Information Bottleneck (VIB)**: Could help with compression/denoising of memory embeddings
3. **Optimal Transport Attention**: Better distribution matching for retrieval — could improve vocabulary matching
4. **Sliced Wasserstein Attention**: Earth mover distance for embedding comparison
5. **Topology-Gated Attention**: Adaptive mode switching based on coherence

### Verdict
The `ruvector-attention` crate is primarily for **transformer model architectures**, not CTC-based transcription. For BeKindRewindAI:
- **Direct improvement to transcription**: No
- **Potential improvement to vocabulary/memory encoding**: Only if using transformer-based encoding
- **Best use case**: If replacing Whisper with a transformer-based ASR model, or if adding a transformer-based encoder layer

### No Python Bindings Limitation
Without PyO3 bindings, integrating this into BeKindRewindAI's Python codebase would require:
- Node.js FFI wrapper
- WebAssembly (Pyodide)
- REST API call to a separate service

This adds significant complexity for marginal benefit since the transcriber (Whisper) wouldn't directly benefit.

---

## Summary Table

| Aspect | Details |
|--------|---------|
| **Mechanisms** | 46 total: Flash, Linear, Multi-Head, Hyperbolic, MoE, Graph, OT, Diffusion, VIB |
| **WASM** | Full support via `ruvector-attention-wasm` v2.1.0, browser + Node.js |
| **Benchmarks** | Flash: 2.3x faster, 5x less memory; Linear: O(n) for seq>4096 |
| **Python** | No PyO3 bindings; WASM/npm only |
| **CLI** | No standalone CLI |
| **BeKindRewindAI Relevance** | Low for transcriber (Whisper/CTC); Medium for vocabulary encoding if transformer-based |
