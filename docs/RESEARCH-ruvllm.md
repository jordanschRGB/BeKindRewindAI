# Research: ruvllm — Local LLM Inference Engine

## 1. What is ruvllm — Engine or Wrapper?

**ruvllm is an independent LLM inference runtime, NOT a wrapper** around llama.cpp, vLLM, or Ollama. It has its own backend implementations:

| Backend | Best For | Acceleration |
|---------|----------|--------------|
| **Candle** | Single user, edge, WASM | Metal, CUDA, CPU |
| **Core ML** | Apple Silicon efficiency | Apple Neural Engine (38 TOPS) |
| **Hybrid Pipeline** | Maximum Mac throughput | GPU for attention + ANE for MLP |
| **mistral-rs** | Production (10-100 users) | PagedAttention, X-LoRA, ISQ |

The Candle backend (from HuggingFace's Candle crate) provides the actual tensor computations. mistral-rs is a separate high-performance serving backend (not yet on crates.io — integration is "designed and ready" but the dependency is unavailable).

---

## 2. Model Formats Supported

**GGUF is the primary format.** No ONNX, no safetensors as a runtime target.

Supported model families:
- **RuvLTRA-Small** (494M) / **RuvLTRA-Medium** (3B) — custom Claude Flow optimized models
- **Llama 3.x** (8B–70B)
- **Qwen 2.5** (0.5B–72B)
- **Mistral** (7B–22B)
- **Phi-3** (3.8B–14B)
- **Gemma-2** (2B–27B)

Quantization levels: Q4K, Q5K, Q8, FP16 via memory-mapped GGUF loading.

---

## 3. WASM Inference — Can It Run an LLM in a Browser?

**Yes, technically — but with constraints.** ruvllm-wasm v2.0.0 uses WebGPU (not WebAssembly SIMD) for acceleration. The WASM package is 83 KB (crate size), runtime is ~5.5 KB. Supported browsers: Chrome 57+, Firefox 52+, Safari 11+, Edge 16+.

Architecture: `JavaScript/TS → wasm-bindgen → RuvLLM Core (Rust WASM) → WebGPU`

The WASM build exposes:
- `RuvLLMWasm` — main inference engine
- `KvCacheWasm` — two-tier KV cache (FP16 tail + quantized store)
- `IntelligentLLMWasm` — SONA learning + HNSW routing + MicroLoRA in browser
- `ChatTemplateWasm` — Llama3, Mistral, Qwen, Phi, Gemma chat formatting
- Web Workers support for parallel inference

**Key limitation**: The browser must have WebGPU support (Chrome/Edge on modern GPUs, Safari Tech Preview). The model weights still need to be loaded — for a 7B Q4K model that is ~4 GB of data that must be fetched and stored in GPU memory. This is impractical for real browser use with current hardware unless the model is tiny (<500M parameters).

**Verdict**: The runtime and inference engine work in WASM. The model loading/fetching is the practical bottleneck for browser use. A 494M RuvLTRA-Small model would be the realistic target for WASM.

---

## 4. Comparison to Ollama, llama.cpp, exllamav2

| Dimension | ruvllm | Ollama | llama.cpp | exllamav2 |
|-----------|--------|--------|-----------|-----------|
| Raw inference speed | Same ballpark | Same ballpark | Same ballpark | Same ballpark |
| Self-learning | **SONA 3-tier loops** | No | No | No |
| Per-request adaptation | **MicroLoRA <1ms** | No | No | No |
| Built-in vector DB | **RuVector HNSW** | No | No | No |
| WASM/Browser | **Yes** | No | No | No |
| Apple Neural Engine | **Yes (38 TOPS)** | No | No | No |
| Continuous batching | Yes | Limited | No | Yes |
| Production serving | mistral-rs backend | Server mode | Server mode | Native |
| Python access | npm package | Native | PyO3 bindings | PyEXLLM |
| ONNX support | No | No | No | No |
| GGUF support | Yes | Yes | Yes | Partial |

**ruvllm's unique differentiators**: SONA self-learning (adapts to queries over time), MicroLoRA per-request fine-tuning in <1ms, integrated RuVector HNSW memory, and WASM/browser support. It is NOT faster for raw inference than llama.cpp/Ollama — the benchmarks show comparable tok/s numbers.

exllamav2 is not mentioned anywhere in ruvllm docs — they are completely unrelated projects.

---

## 5. Could BeKindRewindAI Use This Instead of External AI APIs?

**Partial replacement viable** — not a full swap for OpenAI/Anthropic.

### What works:
- **Local inference for labeling/evaluation**: A 7B Q4K model (Qwen2.5 or Llama3) running at 88–135 tok/s decode is viable for AIJudge/Dreamer replacement on a modern Mac with 16GB RAM
- **RuVector HNSW integration**: Native vocabulary/memory recall — excellent fit for Dreamer agent
- **SONA learning**: Continuous improvement from user feedback — potentially useful for label quality over time
- **OpenAI-compatible server mode**: `ruvllm serve qwen` exposes `/v1/chat/completions`, `/v1/completions`, `/health` — drop-in for code that already calls OpenAI

### What doesn't work:
- **No native Python bindings** — requires subprocess wrapper (`ruvllm-cli`) or HTTP server calls. Any Python integration adds wrapper overhead.
- **No PyO3/native Rust → Python bridge** — the npm package is Node.js only
- **Model quality**: A 7B Q4K local model is noticeably weaker than GPT-4 class models for complex reasoning tasks
- **Memory requirements**: 16GB RAM minimum for 7B Q4K — not all devices qualify
- **New/experimental**: v2.5.4 (March 2026), no published production case studies

### Practical architecture for BeKindRewindAI:
```
BeKindRewindAI (Node.js)
    |
    +-- HTTP POST /v1/chat/completions --> ruvllm serve qwen (local)
```

Or via CLI subprocess: `npx @ruvector/ruvllm-cli generate --model qwen2.5-7b-q4_k.gguf --prompt "..."`

---

## 6. Performance — Tokens/Second, Memory Usage

### M4 Pro 14-core benchmarks (from ruvllm README):

| Model | Quant | Prefill (tok/s) | Decode (tok/s) | Memory |
|-------|-------|-----------------|----------------|--------|
| Qwen2.5-7B | Q4K | 2,800 | 95 | 4.2 GB |
| Qwen2.5-7B | Q8 | 2,100 | 72 | 7.8 GB |
| Llama3-8B | Q4K | 2,600 | 88 | 4.8 GB |
| Mistral-7B | Q4K | 2,500 | 85 | 4.1 GB |
| Phi-3-3.8B | Q4K | 3,500 | **135** | 2.3 GB |
| Gemma2-9B | Q4K | 2,200 | 75 | 5.2 GB |

Decode speeds are comparable to Ollama on the same hardware (~80–100 tok/s for 7B Q4K).

### ANE vs GPU routing on M4 Pro:
- Dimensions <512: ANE 30–50% faster
- Dimensions 512–1024: ANE 10–30% faster
- Dimensions 1024–1536: Similar
- Dimensions >1536: GPU 10–50% faster

### Kernel benchmarks (M4 Pro single-thread vs 10-thread):
- GEMM 4096×4096: 1.2 GFLOPS → 12.7 GFLOPS (10-core)
- Flash Attention (seq=2048): 850μs → 320μs (10-core)
- RMS Norm (4096): 2.1μs → 0.8μs (10-core)

### Hardware requirements:
- **Apple Silicon**: 8GB RAM minimum for 7B Q4K, 16GB recommended. Metal + ANE.
- **NVIDIA GPU**: 6GB VRAM minimum for 7B Q4K, 12GB+ for 13B+. CUDA 11.x/12.x.
- **CPU-only**: 16GB+ RAM, ~10–30 tok/s for 7B Q4K (significantly slower).
- **WASM**: WebGPU required, realistic for models ≤500M parameters in browser.

### CLI access via ruvllm-cli:
```bash
# Install
cargo install ruvllm-cli  # or: npm install @ruvector/ruvllm-cli

# Download model
ruvllm download qwen

# Chat
ruvllm chat qwen

# OpenAI-compatible server
ruvllm serve qwen --port 8080

# Benchmark
ruvllm benchmark qwen --warmup 5 --iterations 20
```

---

## Summary

| Question | Answer |
|----------|--------|
| Engine or wrapper? | Independent runtime — Candle + mistral-rs backends, NOT llama.cpp/vLLM/Ollama |
| Model formats | GGUF only (Q4K/Q5K/Q8/FP16) — RuvLTRA, Llama 3.x, Qwen 2.5, Mistral, Phi-3, Gemma-2. No ONNX. |
| WASM/browser? | Works via WebGPU, realistic for ≤500M models. 4GB model weights still must be loaded in browser. |
| vs Ollama/llama.cpp? | Comparable raw speed, but SONA self-learning + MicroLoRA + RuVector integration are unique differentiators |
| Replace OpenAI for BeKindRewindAI? | Partially — viable for labeling/memory on 16GB+ Macs, but no Python bindings and weaker model quality |
| Performance? | 88–135 tok/s decode for 7B Q4K on M4 Pro, 2.3–5.2 GB memory. Comparable to Ollama. |

## Key Gaps / Concerns

1. **No Python bindings** — any Python integration requires subprocess or HTTP server overhead
2. **mistral-rs not on crates.io** — production backend unavailable, integration is "designed and ready"
3. **New/experimental** — v2.5.4, no published production case studies
4. **No ONNX support** — cannot use models exported in ONNX format
5. **SONA quality improvements unproven** — no benchmarks showing labeling task quality improvement from self-learning
6. **Browser WASM practical limit** — ~500M max model size in practice due to weight loading
