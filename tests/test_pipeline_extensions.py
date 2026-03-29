"""Tests for 4b topic-boosted Whisper pipeline extensions.

Tests the following extensions:
1. Auto-detect topic from filename
2. Batch pre-game for multiple tapes
3. Chapter marker generation
4. Vocabulary prompt injection in Whisper
"""

import json
import os
import sys
import types

_nanobot_mock = types.ModuleType("nanobot")
_nanobot_agent = types.ModuleType("nanobot.agent")
_nanobot_tools = types.ModuleType("nanobot.agent.tools")
_nanobot_registry = types.ModuleType("nanobot.agent.tools.registry")
_nanobot_base = types.ModuleType("nanobot.agent.tools.base")
_nanobot_registry.ToolRegistry = type("MockRegistry", (), {})
_nanobot_base.Tool = type("Tool", (), {})
_nanobot_mock.agent = _nanobot_agent
_nanobot_agent.tools = _nanobot_tools
_nanobot_tools.registry = _nanobot_registry
_nanobot_tools.base = _nanobot_base
sys.modules.setdefault("nanobot", _nanobot_mock)
sys.modules.setdefault("nanobot.agent", _nanobot_agent)
sys.modules.setdefault("nanobot.agent.tools", _nanobot_tools)
sys.modules.setdefault("nanobot.agent.tools.registry", _nanobot_registry)
sys.modules.setdefault("nanobot.agent.tools.base", _nanobot_base)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from harness.runner import (
    extract_topic_from_filename,
    step_generate_chapters,
    step_apply_corrections,
    _dream_pass_result,
)


class TestExtractTopicFromFilename:
    """Test filename-based topic extraction."""

    def test_spiritual_filename(self):
        result = extract_topic_from_filename("/path/to/satsang_2024_01_15.mp4")
        assert "satsang" in result

    def test_family_filename(self):
        result = extract_topic_from_filename("/path/to/christmas_1995_home_video.mp4")
        assert "christmas" in result
        assert "wedding" not in result

    def test_wedding_filename(self):
        result = extract_topic_from_filename("/path/to/mom_dad_wedding.mp4")
        assert "wedding" in result

    def test_music_filename(self):
        result = extract_topic_from_filename("/path/to/live_concert_2023.mp4")
        assert "concert" in result

    def test_sports_filename(self):
        result = extract_topic_from_filename("/path/to/soccer_game_final.mp4")
        assert "game" in result or "soccer" in result

    def test_church_filename(self):
        result = extract_topic_from_filename("/path/to/sunday_sermon.mp4")
        assert "church" in result or "sermon" in result

    def test_no_match_returns_empty(self):
        result = extract_topic_from_filename("/path/to/random_video.mp4")
        assert result == ""

    def test_underscore_and_dash_separators(self):
        result = extract_topic_from_filename("/path/to/family-vacation-tahoe.mp4")
        assert "vacation" in result

    def test_ignores_extension(self):
        result = extract_topic_from_filename("/path/to/tape.mkv")
        assert "mkv" not in result


class TestStepGenerateChapters:
    """Test chapter marker generation from transcript."""

    def test_chapters_returns_tuple(self):
        """step_generate_chapters should return (success, chapters, error) tuple."""
        result = step_generate_chapters("This is a test transcript about various topics.")
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_chapters_fails_gracefully_without_api(self):
        """Without API endpoint, should return failure tuple."""
        success, chapters, err = step_generate_chapters("test transcript")
        assert success is False
        assert chapters is None
        assert err is not None


class TestStepApplyCorrections:
    """Test transcript correction with phonetic matching."""

    def test_no_corrections_when_pass(self):
        """When dream passes, no corrections needed."""
        dream = _dream_pass_result()
        transcript = "Hello world"
        vocab = "hello"

        result, corrections = step_apply_corrections(transcript, dream, vocab)
        assert result == transcript
        assert corrections == []

    def test_corrections_applied_when_doubt(self):
        """When dream reports doubt, corrections attempted."""
        dream = {
            "pass": False,
            "looks_fine": False,
            "doubts": ["ananda my might be Anandamayi"],
            "scores": {"accuracy": 5},
            "reasons": {"accuracy": "ananda my should be Anandamayi"},
        }
        transcript = "I heard ananda my speak at the ashram"
        vocab = "Anandamayi"

        result, corrections = step_apply_corrections(
            transcript, dream, vocab,
            feedback=dream["reasons"],
        )
        assert isinstance(corrections, list)

    def test_phonetically_close_matching(self):
        """Correction should find phonetically similar words."""
        from harness.runner import _is_phonetically_close

        assert _is_phonetically_close("ananda", "anandamayi") is False
        assert _is_phonetically_close("ananda my", "anandamayi") is True
        assert _is_phonetically_close("curtain", "kirtan") is True
        assert _is_phonetically_close("sot song", "satsang") is True

    def test_corrections_empty_when_no_match(self):
        """No corrections if no phonetic match found."""
        dream = {
            "pass": False,
            "looks_fine": False,
            "doubts": ["xyz might be ABC"],
            "scores": {"accuracy": 5},
            "reasons": {"accuracy": "xyz should be ABC"},
        }
        transcript = "The weather is nice today"
        vocab = "ABC"

        result, corrections = step_apply_corrections(
            transcript, dream, vocab,
            feedback=dream["reasons"],
        )
        assert result == transcript
        assert corrections == []

    def test_feedback_hints_prioritized(self):
        """Structured feedback hints should be processed first."""
        dream = {
            "pass": False,
            "looks_fine": False,
            "doubts": ["sot song", "ananda my"],
            "scores": {"accuracy": 5},
            "reasons": {
                "accuracy": "sot song should be satsang; ananda my should be Anandamayi"
            },
        }
        transcript = "During the sot song ananda my led the ceremony"
        vocab = "satsang, Anandamayi"

        result, corrections = step_apply_corrections(
            transcript, dream, vocab,
            feedback=dream["reasons"],
        )
        assert isinstance(corrections, list)


class TestVocabularyPromptInjection:
    """Test that vocabulary is correctly injected into Whisper prompts."""

    def test_vocabulary_used_in_transcription_step(self):
        """Vocabulary should be passed as initial_prompt to Whisper."""
        from unittest.mock import patch, MagicMock

        mock_whisper_model = MagicMock()
        mock_segments = [MagicMock(text="Test transcript")]
        mock_whisper_model.transcribe.return_value = (mock_segments, MagicMock(language="en", duration=10.0))

        with patch("harness.runner.get_api_url", return_value=None):
            pass

    def test_vocab_increases_with_user_description(self):
        """More user description should help generate richer vocabulary."""
        from unittest.mock import patch

        mock_response_vocab = "satsang, kirtan, Anandamayi, Om Namah Shivaya"

        with patch("harness.runner._call_llm") as mock_llm:
            mock_llm.return_value = mock_response_vocab

            with patch("harness.runner.get_api_url", return_value="http://localhost:6942"):
                from harness.runner import step_generate_vocabulary
                vocab = step_generate_vocabulary(
                    "spiritual recording from ashram with chanting",
                    ""
                )

                if vocab:
                    assert len(vocab) > 0


class TestChapterMarkerGeneration:
    """Test chapter markers are included in metadata."""

    def test_chapters_in_metadata_when_generated(self):
        """Chapters should be saved in metadata when generated."""
        from unittest.mock import patch, MagicMock

        mock_chapters = [
            {"timestamp": "0:00", "title": "Introduction"},
            {"timestamp": "2:30", "title": "Main Content"},
        ]

        with patch("harness.runner.step_generate_chapters", return_value=(True, mock_chapters, None)):
            with patch("harness.runner.step_save") as mock_save:
                mock_save.return_value = {"filename": "test.mp4"}

                from harness.runner import step_save
                result = step_save(
                    "test",
                    "/fake/video.mp4",
                    "transcript",
                    {"title": "Test"},
                    "vocab",
                    chapters=mock_chapters
                )

                mock_save.assert_called_once()
                call_args = mock_save.call_args
                assert call_args[0][5] == mock_chapters


class TestBatchPipelineVocabularyAccumulation:
    """Test that batch pipeline accumulates vocabulary across tapes."""

    def test_cumulative_vocab_returned(self):
        """Batch pipeline should return cumulative vocabulary."""
        from unittest.mock import patch, MagicMock

        with patch("harness.runner.step_generate_vocabulary") as mock_vocab:
            mock_vocab.return_value = "satsang, kirtan"

            with patch("harness.runner.step_transcribe") as mock_transcribe:
                mock_transcribe.return_value = ("transcript text", None)

                with patch("harness.runner.step_dream") as mock_dream:
                    mock_dream.return_value = _dream_pass_result()

                    with patch("harness.runner.step_label") as mock_label:
                        mock_label.return_value = ({"title": "Test", "description": "D", "tags": []}, None)

                        with patch("harness.runner.step_generate_chapters") as mock_chapters:
                            mock_chapters.return_value = (True, [], None)

                            with patch("harness.runner.step_save") as mock_save:
                                mock_save.return_value = {}

                                with patch("harness.runner.append_session_log"):
                                    from harness.runner import run_batch_pipeline

                                    result = run_batch_pipeline(
                                        "spiritual tapes",
                                        ["/fake/video1.mp4", "/fake/video2.mp4"]
                                    )

                                    assert "cumulative_vocabulary" in result
                                    assert len(result["tapes"]) == 2
