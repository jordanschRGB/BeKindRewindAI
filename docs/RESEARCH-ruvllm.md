# Research: ruvllm — Local LLM Inference Wrapper

**Bead**: cd039b00-0fc2-47dd-aadb-c6e424c00fbc  
**Crates.io**: [ruvllm](https://crates.io/crates/ruvllm) v2.1.0 | [npm](https://www.npmjs.com/package/@ruvector/ruvllm) v2.4.1  
**GitHub**: [ruvnet/RuVector](https://github.com/ruvnet/ruvector) (3.7k stars)  
**Architecture doc**: [ADR-002](https://github.com/ruvnet/ruvector/blob/main/docs/adr/ADR-002-ruvllm-integration.md)

---

## 1. What LLM Inference It Wraps

**ruvllm is NOT a wrapper around llama.cpp, vLLM, or Ollama.** It is an independent, native Rust LLM inference runtime with its own backend implementations.

### Backend Architecture

```
Source: crates/ruvllm/src/backends/
├── candle_backend.rs    # Primary: HuggingFace Candle ML framework
├── coreml_backend.rs    # Apple Silicon: Core ML + ANE
├── hybrid_pipeline.rs   # Mac: GPU attention + ANE MLP
├── mistral_backend.rs   # Production: mistral-rs (PagedAttention, X-LoRA, ISQ)
├── gemma2.rs            # Model-specific kernels
└── phi3.rs              # Model-specific kernels
```

| Backend | Best For | Acceleration | crates.io |
|---------|----------|--------------|-----------|
| **Candle** | Single user, edge, WASM | Metal, CUDA, CPU | Yes |
| **Core ML** | Apple Silicon efficiency | Apple Neural Engine (38 TOPS) | Yes |
| **Hybrid Pipeline** | Maximum Mac throughput | GPU for attention + ANE for MLP | Yes |
| **mistral-rs** | Production (10-100 users) | PagedAttention, X-LoRA, ISQ | **No** |

**Critical**: The mistral-rs backend (for 50+ concurrent users) is "designed and ready" but **not published to crates.io**. The integration is incomplete.

### Supported Models (GGUF format)

- **RuvLTRA-Small** (494M) / **RuvLTRA-Medium** (3B) — custom Claude Flow optimized
- **Llama 3.x** (8B-70B)
- **Qwen 2.5** (0.5B-72B)
- **Mistral** (7B-22B)
- **Phi-3** (3.8B-14B)
- **Gemma-2** (2B-27B)

Quantization: Q4K, Q5K, Q8, FP16

### Key Technical Differentiators

| Feature | Description | Benefit |
|---------|-------------|---------|
| **SONA** | Self-Optimizing Neural Architecture — three-tier learning loop | Adapts to queries over time without retraining |
| **TurboQuant KV-Cache** | 2-4 bit asymmetric per-channel quantization | 6-8x memory reduction, <0.5% perplexity loss |
| **Flash Attention 2** | O(N) memory complexity, online softmax | Longer contexts with less memory |
| **MicroLoRA** | Per-request fine-tuning in <1ms (rank 1-2) | Personalize responses without full retraining |
| **Speculative Decoding** | Draft model + target verification | 2-3x faster generation |
| **Continuous Batching** | Dynamic batch scheduling | 2-3x throughput improvement |
| **Two-tier KV Cache** | Recent tokens in FP16, older in Q4 | Memory efficiency + quality tradeoff |
| **mistral-rs Backend** | PagedAttention, X-LoRA, ISQ | 5-10x concurrent users vs Candle |

---

## 2. How to Call It from Python

### Option A: npm Package (Node.js/TypeScript)

```bash
npm install @ruvector/ruvllm
```

```javascript
import { RuvLLM } from '@ruvector/ruvllm';

const llm = new RuvLLM({
  model: './models/qwen2.5-7b-q4_k.gguf',
  backend: 'metal' // or 'cuda', 'cpu'
});

const response = await llm.generate("Explain quantum computing", {
  maxTokens: 256,
  temperature: 0.7
});
```

### Option B: CLI Subprocess

```bash
npm install @ruvector/ruvllm-cli
ruvllm-cli generate --model qwen2.5-7b-q4_k.gguf --prompt "Hello"
```

### Option C: WASM in Browser

```bash
npm install @ruvector/ruvllm-wasm
```

```javascript
import init, { WasmSonaEngine } from '@ruvector/ruvllm-wasm';
await init();
const engine = new WasmSonaEngine(256);
```

### Option D: HTTP Server (production-style)

Run ruvllm as HTTP server, call from Python via `requests`:

```python
import requests

response = requests.post("http://localhost:8080/generate", json={
    "model": "qwen2.5-7b-q4_k.gguf",
    "prompt": "Explain quantum computing",
    "max_tokens": 256,
    "temperature": 0.7
})
```

### Python Integration Path (Current Reality)

**No native Python bindings exist.** To use ruvllm from Python:

1. **Subprocess wrapper** — call `ruvllm-cli` as external process
2. **HTTP server mode** — run ruvllm as HTTP server, call from Python via `requests`
3. **Node.js FFI** — use `node-ffi` or similar to call npm package

```python
import subprocess
import json

result = subprocess.run([
    'npx', '@ruvector/ruvllm-cli', 'generate',
    '--model', 'qwen2.5-7b-q4_k.gguf',
    '--prompt', 'Explain quantum computing'
], capture_output=True, text=True)
```

**Note**: This is essentially what BeKindRewindAI already does with external API calls — just swapping one subprocess call for another. The difference is data privacy (local model) and cost (free after hardware).

---

## 3. Performance vs Direct llama.cpp or Ollama

### Published Benchmarks (M4 Pro 14-core, Metal GPU)

| Model | Quant | Prefill (tok/s) | Decode (tok/s) | Memory |
|-------|-------|-----------------|----------------|--------|
| Qwen2.5-7B | Q4K | 2,800 | 95 | 4.2 GB |
| Qwen2.5-7B | Q8 | 2,100 | 72 | 7.8 GB |
| Llama3-8B | Q4K | 2,600 | 88 | 4.8 GB |
| Mistral-7B | Q4K | 2,500 | 85 | 4.1 GB |
| Phi-3-3.8B | Q4K | 3,500 | 135 | 2.3 GB |
| Gemma2-9B | Q4K | 2,200 | 75 | 5.2 GB |

### Comparison with Published Ollama (M4 Pro approximate)

Ollama with Qwen2.5-7B-Q4_K on M4 Pro typically achieves:
- Prefill: ~2,000-2,500 tok/s
- Decode: ~80-100 tok/s

**ruvllm numbers are in the same ballpark** — no clear advantage for pure inference speed.

### ANE vs GPU Performance (M4 Pro)

| Dimension | ANE | GPU | Winner |
|-----------|-----|-----|--------|
| < 512 | +30-50% | — | ANE |
| 512-1024 | +10-30% | — | ANE |
| 1024-1536 | ~Similar | ~Similar | Either |
| 1536-2048 | — | +10-20% | GPU |
| > 2048 | — | +30-50% | GPU |

### Where ruvllm Actually Wins

| Capability | ruvllm | llama.cpp/Ollama |
|------------|--------|------------------|
| Self-learning (SONA) | Yes — adapts over time | No — static |
| Per-request MicroLoRA | <1ms adaptation | No |
| Built-in vector DB | RuVector HNSW integration | No |
| WASM support | Yes (5.5 KB runtime) | No |
| Apple Neural Engine | Yes (38 TOPS) | No |
| Continuous batching | Yes | Ollama: limited |
| Two-tier KV cache | Yes (FP16 + Q4) | No |

**Bottom line**: ruvllm is **not faster** than llama.cpp/Ollama for raw inference. Its value is SONA self-learning, MicroLoRA adaptation, and integrated vector memory — not raw throughput.

---

## 4. BeKindRewindAI AIJudge/Dreamer Replacement Analysis

### Current BeKindRewindAI Architecture

The codebase shows a **3-agent pipeline**:

1. **Archivist** (`MemoryVaultAgent` in agent.py) — conversational interface, drives pipeline
2. **Worker** (`worker_generate_vocabulary()` in agent.py) — generates Whisper vocabulary, labels
3. **Scorer** (`scorer_rate_output()` in agent.py) — rates label quality with 4-criterion rubric

The "Dreamer" (mentioned in the bead) is the **grading rubric agent** in `runner.py` that evaluates transcripts against vocabulary.

**Current LLM calls** (`engine/labeler.py`):
```python
_call_api(messages, api_url=api_url, api_key=api_key, model=model_name)
```

This is an **external API call** — could be OpenAI, Ollama, or any OpenAI-compatible API.

### ruvllm Enhancement Potential

| Function | Current | ruvllm Capability | Fit |
|----------|---------|-------------------|-----|
| LLM inference for grading | External API (OpenAI/Ollama) | GGUF local models | **Good** — replace API |
| Vocabulary generation | External API | GGUF local models | **Good** — replace API |
| Memory/vocabulary search | RuVector HNSW (harness/memory.py) | RuVector HNSW integration | **Excellent** — already native |
| Adaptive learning | Static vocabulary | SONA 3-tier loops | **Excellent** — unique |
| Per-request domain adaptation | None | MicroLoRA <1ms | **Excellent** — unique |

### Replacement Recommendation

**Partial replacement viable — with significant caveats:**

**What CAN be replaced:**
1. Replace OpenAI API calls for grading/labeling with local Qwen2.5-7B-Q4K at 88-135 tok/s decode
2. The vocabulary generation and scoring prompts already produce structured JSON — compatible with local inference

**What CANNOT easily be replaced:**
1. **No Python bindings** — requires subprocess wrapper or HTTP server overhead
2. **SONA learning benefits unproven** for this specific task — no benchmarks for transcript grading
3. **mistral-rs backend unavailable** — production scaling not possible yet

### Specific Integration Path for BeKindRewindAI

```python
# Option: Subprocess wrapper for ruvllm
import subprocess
import json

def call_ruvllm(prompt, system=None, max_tokens=256):
    # Build CLI command
    cmd = [
        'npx', '@ruvector/ruvllm-cli', 'generate',
        '--model', 'qwen2.5-7b-q4_k.gguf',
        '--prompt', prompt,
        '--max-tokens', str(max_tokens),
        '--temperature', '0.7'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

# Use instead of _call_api in:
# - worker_generate_vocabulary()
# - scorer_rate_output()
```

**But this is essentially the same architecture as using Ollama** — a local subprocess call. The advantage of ruvllm is SONA + MicroLoRA, not raw performance.

### MicroLoRA for Domain Adaptation

ruvllm's **MicroLoRA** could be particularly valuable for BeKindRewindAI:

```rust
// Per-request adaptation in <1ms
let feedback = AdaptFeedback::from_quality(0.9);
lora.adapt(&input_embedding, feedback)?;  // Learn from grading corrections
lora.apply_updates(0.01);  // Apply learned updates
```

This could allow the system to **adapt to user's vocabulary domain** (spiritual, family, sports, etc.) over time without full retraining.

### SONA Three-Tier Learning

```rust
// Instant Loop (<1ms): Per-request MicroLoRA
let result = sona.instant_adapt("user query", "model response", 0.85);

// Background Loop (~100ms): Pattern consolidation  
if let result = sona.maybe_background() {
    if result.applied {
        println!("Consolidated {} samples", result.samples_used);
    }
}

// Deep Loop (minutes): Full optimization
if sona.should_trigger_deep() {
    let result = sona.deep_optimize(OptimizationTrigger::QualityThreshold(100.0));
}
```

For BeKindRewindAI, this could mean:
- **Instant**: Learning from each grading correction
- **Background**: Consolidating domain-specific vocabulary patterns
- **Deep**: Full model adaptation for the user's vocabulary domain

---

## 5. Hardware Requirements

### Apple Silicon Mac

| Component | Requirement | Notes |
|-----------|-------------|-------|
| **Metal GPU** | Required | For GPU acceleration |
| **Apple Neural Engine** | Optional | 38 TOPS, 3-4x power efficiency |
| **RAM** | 8GB minimum for 7B Q4K | 16GB recommended |
| **Storage** | 5-10GB per model | GGUF files |

**ANE Routing** (from `hybrid_pipeline.rs`):
- Attention → GPU (better for variable sequence lengths)
- MLP/FFN → ANE (optimal for fixed-size matmuls)
- LayerNorm/RMSNorm → ANE
- Embedding → GPU (sparse operations)

### NVIDIA GPU

| Component | Requirement |
|-----------|-------------|
| **CUDA** | 11.x or 12.x |
| **VRAM** | 6GB minimum for 7B Q4K, 12GB+ for 13B+ |
| **Driver** | Latest CUDA drivers |

### CPU-Only

- RAM: 16GB+ recommended
- Inference: 10-30 tok/s for 7B Q4K (significantly slower)

### WASM/Browser

- WebGPU support required
- Runtime: 5.5 KB
- Use case: Edge deployment, browser-based inference

### Memory Estimates by Model

| Model | Quantization | RAM/VRAM |
|-------|-------------|----------|
| Phi-3-3.8B | Q4K | 2.3 GB |
| Mistral-7B | Q4K | 4.1 GB |
| Qwen2.5-7B | Q4K | 4.2 GB |
| Llama3-8B | Q4K | 4.8 GB |
| Gemma2-9B | Q4K | 5.2 GB |
| Qwen2.5-7B | Q8 | 7.8 GB |
| Llama3-70B | Q4K | ~40 GB |

### Containerized Deployment

```dockerfile
# Not officially published — build from source
FROM rust:1.77-slim
RUN cargo install ruvllm
```

No official Docker images or cross-platform binaries mentioned.

---

## Summary

| Question | Answer |
|----------|--------|
| What does it wrap? | Independent runtime using Candle + mistral-rs, NOT llama.cpp/vLLM |
| Python access? | Via npm (@ruvector/ruvllm) or CLI subprocess — no native PyO3 |
| Performance vs llama.cpp/Ollama? | Similar inference speed, but SONA self-learning is unique differentiator |
| Replace AIJudge/Dreamer? | **Partially** — good for local inference + memory, but no Python bindings |
| Hardware requirements? | Apple Silicon (Metal+ANE) or NVIDIA (CUDA), 6-16GB RAM depending on model |

---

## Key Gaps / Concerns

| Gap | Severity | Impact |
|-----|----------|--------|
| **No Python bindings** | High | Any Python integration requires wrapper overhead (subprocess/HTTP) |
| **mistral-rs not on crates.io** | High | Production backend (50+ users) unavailable — integration is "designed and ready" |
| **New/experimental** | Medium | v2.5.4 (March 2026), no production case studies published |
| **SONA benefits unproven for grading** | Medium | No benchmarks showing quality improvement for transcript evaluation |
| **No M1/M2 Mac benchmarks** | Low | Only M4 Pro numbers available |
| **CLI wrapper overhead** | Medium | Subprocess calls add latency vs native llama.cpp Python bindings |

---

## Alternative: llama.cpp Python vs ruvllm

If the goal is **local inference without API costs**, consider:

| Factor | ruvllm | llama.cpp (llama-cpp-python) |
|--------|--------|------------------------------|
| **Python bindings** | No (npm/CLI only) | **Yes** (PyO3, `llama_cpp_cbert.py`) |
| **Performance** | Similar | Similar |
| **SONA learning** | **Yes** (unique) | No |
| **MicroLoRA** | **Yes** (<1ms) | No |
| **Vector DB integration** | **Yes** (RuVector) | No |
| **WASM support** | **Yes** | No |
| **Apple ANE** | **Yes** | No |
| **Maturity** | New (v2.5) | **Stable** (widely used) |

**Recommendation**: For BeKindRewindAI's current architecture:
1. If you need **SONA + MicroLoRA + vector memory**: ruvllm (with subprocess wrapper)
2. If you just need **local inference**: Use llama.cpp via `llama-cpp-python` directly — it's mature, has native Python bindings, and is widely used

---

## References

- [crates.io](https://crates.io/crates/ruvllm)
- [npm package](https://www.npmjs.com/package/@ruvector/ruvllm)
- [GitHub](https://github.com/ruvnet/ruvector/tree/main/crates/ruvllm)
- [docs.rs](https://docs.rs/ruvllm/latest/ruvllm/)
- [ADR-002 Architecture](https://github.com/ruvnet/ruvector/blob/main/docs/adr/ADR-002-ruvllm-integration.md)
- [llama.cpp vs vLLM vs Ollama benchmarks](https://insiderllm.com/guides/llamacpp-vs-ollama-vs-vllm/)
