# Research: ruvector-cnn — CNN Image Embeddings

## Summary

`ruvector-cnn` converts images into 512-dimensional numerical embeddings (vectors) using a MobileNet-V3 Small CNN backbone. Think of it as a "visual fingerprint" — similar images produce similar vectors.

**MobileNet-V3 Small** is Google's efficient mobile-first architecture: 2.5M parameters, 56M FLOPs, 67.4% ImageNet top-1 accuracy. It's designed for edge/mobile deployment, not maximum accuracy.

**Sub-5ms latency** is achieved through multiple optimizations:
- SIMD kernels (AVX2 on x86_64, NEON on ARM, SIMD128 in WASM)
- 4x unrolled convolutions with 4 independent accumulators for better instruction-level parallelism
- Winograd F(2,3) transforms reducing 3x3 convolution from 36 to 16 multiplications
- Depthwise separable convolutions (8-9x fewer FLOPs than standard)
- π-calibrated INT8 quantization (2-4x faster, 4x smaller memory)

**What you can DO with it:**
- Find visually similar images (cosine similarity on embeddings)
- Cluster image datasets by visual similarity
- Detect near-duplicates across large datasets
- Train custom visual concepts via contrastive losses (InfoNCE, Triplet, NT-Xent)
- Build multimodal search (combine with text embeddings)
- Real-time visual inspection on edge devices

**Python/WASM bindings:**
- WASM: First-class support via `features = ["wasm"]` — compiles to `wasm32-unknown-unknown`. Can run in browser with ~18ms latency.
- Node.js: NAPI-RS bindings via `features = ["napi"]`
- Python: No direct binding documented. Could access via WASM (e.g., pyodide) or mcporter API.

**Use cases for BeKindRewindAI:**
- Generate pixel art backgrounds for TANE-UI by embedding style reference images and searching a catalog
- Cluster captured video frames by visual similarity for scene detection
- Find similar visual content when repurposing archived material
- Edge deployment on low-power devices for on-device inference

**Not recommended for:**
- Maximum accuracy tasks (use ResNet-152 or ViT instead)
- GPU-accelerated training (PyTorch is better)
- Direct Python usage without WASM intermediary

**Verdict:** Useful for fast, portable image embeddings with excellent edge deployment story. The ~2MB binary and <5ms CPU latency make it practical for real-time applications. For BeKindRewindAI, potential use in generating visual content backgrounds or scene clustering, but not directly relevant to audio/video transcription pipeline.
