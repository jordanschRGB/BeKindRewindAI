# Research: ruvllm — Local LLM Inference Crate

## What ruvllm Is

**ruvllm** is an edge-focused LLM serving runtime built in Rust by RuVector. It loads GGUF-format models and runs inference locally on Metal (Apple Silicon), CUDA (NVIDIA), ANE (Apple Neural Engine), WebGPU, or CPU. Unlike llama.cpp or Ollama, it has a self-learning layer called **SONA** that adapts to queries over time with three tiers: instant (<1ms MicroLoRA), background (~100ms pattern consolidation), and deep (minutes-scale full optimization). It also has built-in RuVector integration for vector memory with HNSW routing.

## Model Support

Supports **GGUF format** for all major architectures: Llama 3.x (8B-70B), Qwen 2.5 (0.5B-72B), Mistral (7B-22B), Phi-3 (3.8B-14B), Gemma-2 (2B-27B), and RuVector's own RuvLTRA models (494M and 3B). Quantizations: Q4K, Q5K, Q8, FP16 via memory-mapped GGUF loading.

## Hardware Backends

- **Metal** (Apple Silicon GPU) via Candle backend — best for Mac with M-series chips
- **CUDA** (NVIDIA) — via candle or mistral-rs backend
- **Apple Neural Engine (ANE)** via Core ML — hybrid GPU+ANE pipeline for Mac
- **WebAssembly** — 5.5 KB runtime, can run in browser
- **CPU** — scalar fallback

## Python Integration

**@ruvector/ruvllm** npm package (v2.5.4, published 4 days ago) provides direct Python-accessible bindings via Node.js. Alternatively, use **subprocess** to call the **ruvllm-cli** binary. Python call pattern:

```python
import subprocess

result = subprocess.run(
    ["ruvllm", "query", "--stream", "Explain quantum computing"],
    capture_output=True, text=True
)
print(result.stdout)
```

Or via the npm package in Python (using subprocess to call node):

```python
# Using npm package directly
subprocess.run(["node", "-e", """
const { RuvLLM } = require('@ruvector/ruvllm');
const llm = new RuvLLM({ modelPath: './models/qwen2.5-7b-q4_k.gguf' });
llm.query('Explain quantum computing').then(r => console.log(r.text));
"""])
```

The core API: `RuvLLM.query(prompt, GenerateParams)` returns a Promise with `.text`, or `RuvLLM.stream(prompt)` for streaming tokens.

## WASM Bindings

**Yes** — ruvllm has a `wasm` feature flag and the `@ruvector/ruvllm` npm package works in Node.js and browser environments. The WASM runtime is ~5.5 KB. However, running a full LLM in browser WASM is limited to small models (RuvLTRA-Small 494M at Q4K is the practical ceiling).

## How It Differs from llama.cpp / Ollama

| | ruvllm | llama.cpp | Ollama |
|---|---|---|---|
| Self-learning (SONA) | Yes — adapts over time | No | No |
| MicroLoRA per-request | Yes — <1ms | No | No |
| RuVector integration | Built-in HNSW memory | No | No |
| Apple ANE support | Yes (Core ML + hybrid pipeline) | No | No |
| WASM runtime | Yes — 5.5 KB | No | No |
| mistral-rs backend | Yes (PagedAttention, X-LoRA, ISQ) | No | No |
| Speculative decoding | Yes | Yes | No |
| Continuous batching | Yes | No | No |
| Python-native | Via npm subprocess | PyO3 bindings | Ollama API |

## Key Feature Flags

- `inference-metal` / `inference-metal-native` — Metal GPU inference
- `inference-cuda` — CUDA GPU inference
- `coreml` / `hybrid-ane` — Apple Neural Engine
- `gguf-mmap` — memory-mapped GGUF loading
- `parallel` — Rayon multi-threaded GEMM/GEMV
- `accelerate` — Apple Accelerate BLAS (~2x GEMV speedup)
- `mistral-rs` — production PagedAttention backend
- `wasm` — WebAssembly support
- `hf-hub` — HuggingFace Hub model download

## BeKindRewindAI Integration Path

ruvllm could replace OpenAI API calls for Whisper (via a local Whisper model) and for labeling/categorization. The integration would be:

1. **Python calls ruvllm-cli subprocess** or **node subprocess** running `@ruvector/ruvllm`
2. **Whisper** — use a GGUF Whisper model via ruvllm (if supported) or keep using faster-whisper OpenAI-compatible endpoint
3. **Labeling** — run a local Llama/Qwen GGUF model for zero-shot classification
4. **Trade-off** — 100% offline, no API costs, but needs 4-8GB RAM for a 7B Q4K model and a Mac with Metal or an NVIDIA GPU for real-time performance (88-135 tok/s on M4 Pro)

**Recommended for BeKindRewindAI**: Use ruvllm for the labeling/description generation task (small model like RuvLTRA-Small 494M or Phi-3 Q4K fits easily in RAM), and keep faster-whisper for transcription unless a Whisper GGUF becomes available.
