"""Tests for AI inference engine."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from engine.inference import (
    get_model_dir, get_model_path, is_model_downloaded,
    get_download_status, detect_hardware, MODELS,
)


def test_model_dir_creation(tmp_path, monkeypatch):
    model_dir = str(tmp_path / "models")
    monkeypatch.setattr("engine.inference.MODEL_DIR", model_dir)
    result = get_model_dir()
    assert os.path.isdir(result)


def test_model_path():
    path = get_model_path("qwen-labeler")
    assert path is not None
    assert "Qwen3.5-4B" in path


def test_model_path_unknown():
    path = get_model_path("nonexistent")
    assert path is None


def test_qwen_found_via_local_path(monkeypatch, tmp_path):
    """is_model_downloaded returns True when local_path file exists."""
    fake_model_path = str(tmp_path / "Qwen3.5-4B-Q4_K_M.gguf")
    # Create a fake model file
    with open(fake_model_path, "w") as f:
        f.write("fake")
    # Patch the MODELS registry so local_path points to our fake file
    import engine.inference as inf
    original = inf.MODELS["qwen-labeler"]["local_path"]
    inf.MODELS["qwen-labeler"]["local_path"] = fake_model_path
    try:
        assert inf.is_model_downloaded("qwen-labeler") is True
    finally:
        inf.MODELS["qwen-labeler"]["local_path"] = original


def test_download_status():
    status = get_download_status()
    assert "whisper-asr" in status
    assert "qwen-labeler" in status
    # Qwen model entry is present and has correct filename
    assert "Q4_K_M" in status["qwen-labeler"]["path"]


def test_detect_hardware():
    hw = detect_hardware()
    assert "platform" in hw
    assert "recommended_backend" in hw
    assert hw["recommended_backend"] in ("cuda", "metal", "cpu")


def test_models_registry():
    assert len(MODELS) == 2
    for key, model in MODELS.items():
        assert "name" in model
        assert "filename" in model
        assert "size_mb" in model
        assert "purpose" in model
