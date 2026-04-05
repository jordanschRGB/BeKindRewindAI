# Research: ruvllm — Local LLM Inference Wrapper

## 1. What LLM Inference It Wraps

**ruvllm does NOT wrap llama.cpp, vLLM, or Ollama.** It is an independent LLM inference runtime with its own backend implementations.

### Backends

| Backend | Best For | Acceleration |
|---------|----------|--------------|
| **Candle** | Single user, edge, WASM | Metal, CUDA, CPU |
| **Core ML** | Apple Silicon efficiency | Apple Neural Engine (38 TOPS) |
| **Hybrid Pipeline** | Maximum Mac throughput | GPU for attention + ANE for MLP |
| **mistral-rs** | Production (10-100 users) | PagedAttention, X-LoRA, ISQ |

### Supported Models (GGUF format)

- **RuvLTRA-Small** (494M) / **RuvLTRA-Medium** (3B) — custom Claude Flow optimized
- **Llama 3.x** (8B-70B)
- **Qwen 2.5** (0.5B-72B)
- **Mistral** (7B-22B)
- **Phi-3** (3.8B-14B)
- **Gemma-2** (2B-27B)

Quantization: Q4K, Q5K, Q8, FP16

### Key Technical Differentiators

- **SONA** (Self-Optimizing Neural Architecture) — three-tier learning loop that adapts to queries
- **TurboQuant KV-Cache** — 2-4 bit asymmetric per-channel quantization (6-8x memory reduction, <0.5% perplexity loss)
- **Flash Attention 2** — O(N) memory complexity
- **MicroLoRA** — per-request fine-tuning in <1ms
- **Speculative Decoding** — 2-3x faster generation
- **Continuous Batching** — 2-3x throughput improvement
- **Two-tier KV Cache** — recent tokens in FP16, older in Q4

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

### Python Integration Path

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

---

## 3. Performance vs Direct llama.cpp or Ollama

### Published Benchmarks (M4 Pro 14-core)

| Model | Quant | Prefill (tok/s) | Decode (tok/s) | Memory |
|-------|-------|-----------------|----------------|--------|
| Qwen2.5-7B | Q4K | 2,800 | 95 | 4.2 GB |
| Qwen2.5-7B | Q8 | 2,100 | 72 | 7.8 GB |
| Llama3-8B | Q4K | 2,600 | 88 | 4.8 GB |
| Mistral-7B | Q4K | 2,500 | 85 | 4.1 GB |
| Phi-3-3.8B | Q4K | 3,500 | 135 | 2.3 GB |

### Comparison with Published Ollama (M4 Pro approximate)

Ollama with Qwen2.5-7B-Q4_K on M4 Pro typically achieves:
- Prefill: ~2,000-2,500 tok/s
- Decode: ~80-100 tok/s

**ruvllm numbers are in the same ballpark** — no clear advantage for pure inference speed.

### Where ruvllm Differs

| Capability | ruvllm | llama.cpp/Ollama |
|------------|--------|------------------|
| Self-learning (SONA) | Yes — adapts over time | No — static |
| Per-request MicroLoRA | <1ms adaptation | No |
| Built-in vector DB | RuVector HNSW integration | No |
| WASM support | Yes | No |
| Apple Neural Engine | Yes (38 TOPS) | No |
| Continuous batching | Yes | Ollama: limited |

**Bottom line**: ruvllm is not faster than llama.cpp/Ollama for raw inference. Its value is SONA self-learning, MicroLoRA adaptation, and integrated vector memory.

---

## 4. BeKindRewindAI AIJudge/Dreamer Replacement Analysis

### Current AIJudge/Dreamer Functionality

Based on BeKindRewindAI architecture (3-agent pipeline: Orchestrator/Agent/Dreamer), the Dreamer agent likely:
- Evaluates response quality
- Stores/retrieves memories
- Provides feedback for improvement

### ruvllm Enhancement Potential

| Function | ruvllm Capability | Fit |
|----------|-------------------|-----|
| LLM inference for judgment | GGUF local models | Good — replace OpenAI |
| Memory/vocabulary search | RuVector HNSW integration | Excellent — native |
| Adaptive learning | SONA 3-tier loops | Excellent — unique |
| Per-request adaptation | MicroLoRA <1ms | Excellent — no retraining |
| Real-time transcription | Streaming + Flash Attention | Moderate |

### Replacement Recommendation

**Partial replacement viable:**

1. **Replace OpenAI API calls** for labeling/evaluation with local Qwen2.5-7B-Q4K at 88-135 tok/s decode
2. **Enhance Dreamer memory** with RuVector HNSW for vocabulary recall
3. **Use SONA learning** for continuous improvement from user feedback

### Caveats

- **No Python bindings** — requires subprocess wrapper or HTTP server
- **New/experimental** — v2.5.4 (March 2026), limited production case studies
- **mistral-rs backend not on crates.io** — integration is "designed and ready" but dependency unavailable
- **SONA learning benefits unclear** — no published benchmarks showing quality improvement for labeling tasks

---

## 5. Hardware Requirements

### Apple Silicon Mac

| Component | Requirement |
|-----------|-------------|
| Metal GPU | Required for GPU acceleration |
| Apple Neural Engine | Optional but recommended |
| RAM | 8GB minimum for 7B Q4K, 16GB recommended |
| Storage | 5-10GB per model |

### NVIDIA GPU

| Component | Requirement |
|-----------|-------------|
| CUDA | 11.x or 12.x |
| VRAM | 6GB minimum for 7B Q4K, 12GB+ for 13B+ |
| Driver | Latest CUDA drivers |

### CPU-Only

- RAM: 16GB+ recommended
- Inference: 10-30 tok/s for 7B Q4K (significantly slower)

### WASM/Browser

- WebGPU support required
- 5.5 KB runtime

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
| Replace AIJudge/Dreamer? | Partially — good for local inference + memory, but no Python bindings |
| Hardware requirements? | Apple Silicon (Metal+ANE) or NVIDIA (CUDA), 6-16GB RAM depending on model |

---

## Key Gaps / Concerns

1. **No Python bindings** — any Python integration requires wrapper overhead
2. **Not on crates.io (mistral-rs)** — production backend unavailable
3. **New/experimental** — v2.5.4, no production case studies published
4. **No M1/M2 Mac benchmarks** — only M4 Pro numbers available
5. **Self-learning benefits unproven** — SONA quality improvements not benchmarked for labeling tasks
