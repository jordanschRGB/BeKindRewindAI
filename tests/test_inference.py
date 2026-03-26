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


def test_qwen_found_via_local_path():
    """Qwen GGUF exists in LM Studio directory."""
    assert is_model_downloaded("qwen-labeler") is True


def test_download_status():
    status = get_download_status()
    assert "whisper-asr" in status
    assert "qwen-labeler" in status
    # Qwen is locally available via LM Studio
    assert status["qwen-labeler"]["downloaded"] is True


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
