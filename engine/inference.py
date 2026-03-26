"""AI inference engine — model download, hardware detection, llama.cpp wrapper."""

import os
import platform
import subprocess
import sys
import urllib.request
import json

# Default model storage
MODEL_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault", "models")

# Model registry — GGUF files from HuggingFace
MODELS = {
    "whisper-asr": {
        "name": "Whisper Small (faster-whisper)",
        "filename": "N/A — managed by faster-whisper",
        "url": "auto",  # faster-whisper downloads from HF automatically
        "size_mb": 460,
        "purpose": "speech-to-text",
    },
    "qwen-labeler": {
        "name": "Qwen 3.5 4B",
        "filename": "Qwen3.5-4B-Q4_K_M.gguf",
        "url": "https://huggingface.co/unsloth/Qwen3.5-4B-GGUF/resolve/main/Qwen3.5-4B-Q4_K_M.gguf",
        "size_mb": 2500,
        "purpose": "labeling",
        "local_path": os.path.join(os.path.expanduser("~"), ".lmstudio", "models", "unsloth", "Qwen3.5-4B-GGUF", "Qwen3.5-4B-Q4_K_M.gguf"),
    },
}


def get_model_dir():
    """Return model storage directory, creating if needed."""
    os.makedirs(MODEL_DIR, exist_ok=True)
    return MODEL_DIR


def get_model_path(model_key):
    """Return full path to a model's GGUF file. Checks local_path first, then MODEL_DIR."""
    model = MODELS.get(model_key)
    if not model:
        return None
    # Check local_path override (e.g. LM Studio shared models)
    local = model.get("local_path")
    if local and os.path.exists(local):
        return local
    return os.path.join(get_model_dir(), model["filename"])


def is_model_downloaded(model_key):
    """Check if a model GGUF file exists on disk."""
    model = MODELS.get(model_key)
    if not model:
        return False
    # Check local_path first
    local = model.get("local_path")
    if local and os.path.exists(local):
        return True
    path = os.path.join(get_model_dir(), model["filename"])
    return os.path.exists(path)


def get_download_status():
    """Return download status for all models."""
    status = {}
    for key, model in MODELS.items():
        path = get_model_path(key)
        status[key] = {
            "name": model["name"],
            "purpose": model["purpose"],
            "size_mb": model["size_mb"],
            "downloaded": os.path.exists(path) if path else False,
            "path": path,
            "url_available": model["url"] is not None,
        }
    return status


def download_model(model_key, progress_callback=None):
    """Download a model GGUF from HuggingFace.

    Args:
        model_key: Key from MODELS dict
        progress_callback: Optional callable(bytes_downloaded, total_bytes)

    Returns:
        (success: bool, error: str|None, path: str|None)
    """
    model = MODELS.get(model_key)
    if not model:
        return False, f"Unknown model: {model_key}", None

    if not model["url"]:
        return False, f"Download URL not yet available for {model['name']}", None

    path = get_model_path(model_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        def _report(block_num, block_size, total_size):
            if progress_callback:
                progress_callback(block_num * block_size, total_size)

        urllib.request.urlretrieve(model["url"], path, reporthook=_report)
        return True, None, path
    except Exception as e:
        # Clean up partial download
        try:
            os.unlink(path)
        except OSError:
            pass
        return False, str(e), None


def detect_hardware():
    """Detect available hardware for inference.

    Returns dict with:
        platform: str (Windows/Darwin/Linux)
        gpu_available: bool
        gpu_name: str|None
        gpu_vram_mb: int|None
        mlx_available: bool (Mac only)
        recommended_backend: str (cuda/metal/cpu)
    """
    info = {
        "platform": platform.system(),
        "gpu_available": False,
        "gpu_name": None,
        "gpu_vram_mb": None,
        "mlx_available": False,
        "recommended_backend": "cpu",
    }

    # Check NVIDIA GPU
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            info["gpu_available"] = True
            info["gpu_name"] = parts[0].strip()
            info["gpu_vram_mb"] = int(float(parts[1].strip()))
            info["recommended_backend"] = "cuda"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check Mac Metal / MLX
    if platform.system() == "Darwin":
        try:
            import mlx
            info["mlx_available"] = True
            info["recommended_backend"] = "metal"
        except ImportError:
            # Metal still available via llama.cpp even without MLX python
            info["recommended_backend"] = "metal"

    return info


class LlamaInference:
    """Wrapper around llama-cpp-python for running GGUF models."""

    def __init__(self, model_path, n_ctx=4096, n_gpu_layers=-1):
        """Load a GGUF model.

        Args:
            model_path: Path to .gguf file
            n_ctx: Context window size
            n_gpu_layers: Layers to offload to GPU (-1 = all)
        """
        self.model_path = model_path
        self.model = None
        self._load(n_ctx, n_gpu_layers)

    def _load(self, n_ctx, n_gpu_layers):
        """Load the model via llama-cpp-python."""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed. "
                "Install with: pip install llama-cpp-python"
            )

        self.model = Llama(
            model_path=self.model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
            verbose=False,
        )

    def generate(self, prompt, max_tokens=512, temperature=0.7, stop=None):
        """Generate text from a prompt.

        Returns:
            str: Generated text
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        output = self.model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
        )

        return output["choices"][0]["text"]

    def chat(self, messages, max_tokens=512, temperature=0.7):
        """Chat completion.

        Args:
            messages: List of {"role": str, "content": str}

        Returns:
            str: Assistant response
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        output = self.model.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return output["choices"][0]["message"]["content"]

    def unload(self):
        """Free model from memory."""
        self.model = None


def ensure_llama_cpp():
    """Check if llama-cpp-python is installed, return (available: bool, error: str|None)."""
    try:
        import llama_cpp
        return True, None
    except ImportError:
        return False, "llama-cpp-python not installed. Run: pip install llama-cpp-python"


def install_llama_cpp():
    """Attempt to install llama-cpp-python.

    Returns (success: bool, error: str|None)
    """
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "llama-cpp-python"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=300,
        )
        return True, None
    except subprocess.CalledProcessError as e:
        return False, f"pip install failed: {e}"
    except subprocess.TimeoutExpired:
        return False, "Installation timed out"
