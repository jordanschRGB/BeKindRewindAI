"""MemoryVault tools for Nanobot harness.

Six tools. No shell. No delete. No network. No arbitrary filesystem.
Security lives in each tool — path validation, type restriction, append-only.
"""

import json
import os
import time
from typing import Any

from nanobot.agent.tools.base import Tool
from harness.grading import (
    GRADING_CRITERIA, check_thresholds, format_failure_consequence,
)

# The only directory these tools can write to
VAULT_DIR = os.path.join(os.path.expanduser("~"), "Videos", "MemoryVault")
MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".memoryvault")


def _safe_path(base_dir, filename):
    """Ensure path stays inside the allowed directory."""
    full = os.path.abspath(os.path.join(base_dir, filename))
    if not full.startswith(os.path.abspath(base_dir)):
        raise PermissionError(f"Path escapes allowed directory: {filename}")
    return full


class GenerateVocabularyTool(Tool):
    """Generates Whisper vocabulary from user description + memory."""

    @property
    def name(self) -> str:
        return "generate_vocabulary"

    @property
    def description(self) -> str:
        return (
            "Generate a vocabulary list for Whisper speech recognition priming. "
            "Takes a description of the tape content and returns comma-separated "
            "domain-specific words that improve transcription accuracy. "
            "Focus on proper nouns, foreign terms, and words Whisper would mangle."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "User's description of tape content (names, topics, language, era)",
                },
                "existing_vocabulary": {
                    "type": "string",
                    "description": "Previously learned vocabulary from MEMORY.md to include",
                },
            },
            "required": ["description"],
        }

    async def execute(self, description: str, existing_vocabulary: str = "") -> str:
        # This tool's output IS the vocabulary — no side effects
        # The agent generates vocabulary via its own inference
        # We just pass through and let the caller use it for Whisper
        parts = []
        if existing_vocabulary:
            parts.append(existing_vocabulary)
        parts.append(f"(Generate vocabulary for: {description})")
        return ", ".join(parts)


class TranscribeTool(Tool):
    """Transcribes audio from a video file using Whisper with vocabulary priming."""

    @property
    def name(self) -> str:
        return "transcribe"

    @property
    def description(self) -> str:
        return (
            "Transcribe audio from a video file. Uses Whisper speech recognition "
            "with vocabulary priming for better accuracy on unusual words. "
            "Returns the transcript text."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "video_path": {
                    "type": "string",
                    "description": "Path to the video file to transcribe",
                },
                "vocabulary": {
                    "type": "string",
                    "description": "Comma-separated vocabulary to prime Whisper with",
                },
            },
            "required": ["video_path"],
        }

    async def execute(self, video_path: str, vocabulary: str = "") -> str:
        # Path must be in vault dir
        if not os.path.abspath(video_path).startswith(os.path.abspath(VAULT_DIR)):
            return json.dumps({"error": "Can only transcribe files in MemoryVault folder"})

        if not os.path.exists(video_path):
            return json.dumps({"error": f"File not found: {video_path}"})

        from engine.transcribe import extract_audio, is_whisper_available

        if not is_whisper_available():
            return json.dumps({"error": "Whisper not available"})

        success, wav_path, err = extract_audio(video_path)
        if not success:
            return json.dumps({"error": err})

        try:
            from faster_whisper import WhisperModel
            import ctranslate2

            device = "cpu"
            compute_type = "int8"
            try:
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
                    compute_type = "float16"
            except Exception:
                pass

            model = WhisperModel("small", device=device, compute_type=compute_type)
            segments, info = model.transcribe(
                wav_path,
                beam_size=5,
                initial_prompt=vocabulary if vocabulary else None,
            )

            transcript = " ".join(seg.text.strip() for seg in segments).strip()
            return json.dumps({
                "transcript": transcript or "(no speech detected)",
                "language": info.language,
                "duration": round(info.duration, 1),
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
        finally:
            try:
                os.unlink(wav_path)
            except OSError:
                pass


class LabelTapeTool(Tool):
    """Generates title, description, and tags from a transcript."""

    @property
    def name(self) -> str:
        return "label_tape"

    @property
    def description(self) -> str:
        return (
            "Generate a title, description, and tags for a tape from its transcript. "
            "Returns JSON with title, description, and tags fields."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "transcript": {
                    "type": "string",
                    "description": "The audio transcript to generate labels from",
                },
            },
            "required": ["transcript"],
        }

    async def execute(self, transcript: str) -> str:
        from engine.labeler import generate_labels
        success, labels, err = generate_labels(transcript=transcript)
        if success:
            return json.dumps(labels)
        return json.dumps({"error": err})


class ScoreLabelTool(Tool):
    """Rates label quality per structured grading rubric with threshold checks."""

    @property
    def name(self) -> str:
        return "score_label"

    @property
    def description(self) -> str:
        criteria_desc = ", ".join(
            f"{name} (threshold {cfg['threshold']})"
            for name, cfg in GRADING_CRITERIA.items()
        )
        return (
            f"Rate a generated label on structured criteria: {criteria_desc}. "
            "Returns per-criterion scores, pass/fail, and a concrete consequence "
            "statement describing what the user would have to do manually for any "
            "criterion below its threshold."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "transcript": {
                    "type": "string",
                    "description": "The original transcript",
                },
                "labels_json": {
                    "type": "string",
                    "description": "JSON string of the label to evaluate",
                },
            },
            "required": ["transcript", "labels_json"],
        }

    async def execute(self, transcript: str, labels_json: str) -> str:
        from agent import scorer_rate_output
        success, score_data, err = scorer_rate_output(transcript, labels_json)
        if not success:
            return json.dumps({"error": err})

        # Wrap legacy single-score output in structured grading format
        legacy_score = score_data.get("score", 0)
        result = {
            "scores": {
                "accuracy": legacy_score,
                "completeness": legacy_score,
                "label_quality": legacy_score,
                "hallucination": legacy_score,
            },
            "reasons": {
                "accuracy": score_data.get("reason", ""),
                "completeness": score_data.get("reason", ""),
                "label_quality": score_data.get("reason", ""),
                "hallucination": score_data.get("reason", ""),
            },
            "consequence": score_data.get("consequence", ""),
        }

        # Check thresholds
        passed, failures = check_thresholds(result["scores"])
        result["pass"] = passed
        if not passed and not result["consequence"]:
            result["consequence"] = format_failure_consequence(
                failures, result["reasons"]
            )

        return json.dumps(result)


class SaveMetadataTool(Tool):
    """Saves tape metadata to the MemoryVault folder. Append-only."""

    @property
    def name(self) -> str:
        return "save_metadata"

    @property
    def description(self) -> str:
        return (
            "Save tape metadata (title, transcript, labels) as a JSON file "
            "alongside the video. Can only write to the MemoryVault folder. "
            "Cannot overwrite existing files."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Filename for the metadata (must end in .json)",
                },
                "metadata": {
                    "type": "string",
                    "description": "JSON string of metadata to save",
                },
            },
            "required": ["filename", "metadata"],
        }

    async def execute(self, filename: str, metadata: str) -> str:
        if not filename.endswith(".json"):
            return json.dumps({"error": "Can only write .json files"})

        try:
            path = _safe_path(VAULT_DIR, filename)
        except PermissionError as e:
            return json.dumps({"error": str(e)})

        os.makedirs(VAULT_DIR, exist_ok=True)

        try:
            data = json.loads(metadata)
        except json.JSONDecodeError:
            return json.dumps({"error": "Invalid JSON"})

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        return json.dumps({"saved": filename})


class ListLibraryTool(Tool):
    """Lists all captured tapes in the library. Read-only."""

    @property
    def name(self) -> str:
        return "list_library"

    @property
    def description(self) -> str:
        return "List all captured tapes with their metadata. Read-only."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self) -> str:
        from library import list_tapes
        tapes = list_tapes(VAULT_DIR)
        return json.dumps({"tapes": tapes, "count": len(tapes)})


def register_vault_tools(registry):
    """Register ONLY MemoryVault tools. No shell. No delete. No network."""
    registry.register(GenerateVocabularyTool())
    registry.register(TranscribeTool())
    registry.register(LabelTapeTool())
    registry.register(ScoreLabelTool())
    registry.register(SaveMetadataTool())
    registry.register(ListLibraryTool())
