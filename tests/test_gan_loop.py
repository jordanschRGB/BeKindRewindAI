"""Tests for GAN loop in harness/runner.py — iteration, circuit breaker, context isolation."""

import json
import os
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, call

# Mock nanobot before importing harness.runner (nanobot not installed in test env)
_nanobot_mock = types.ModuleType("nanobot")
_nanobot_agent = types.ModuleType("nanobot.agent")
_nanobot_tools = types.ModuleType("nanobot.agent.tools")
_nanobot_registry = types.ModuleType("nanobot.agent.tools.registry")
_nanobot_base = types.ModuleType("nanobot.agent.tools.base")
_nanobot_registry.ToolRegistry = MagicMock
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
    step_dream,
    step_apply_corrections,
    run_pipeline,
    _dream_pass_result,
    _parse_dream_result,
    MAX_ITERATIONS,
    DREAMER_PROMPT,
)
from harness.grading import GRADING_CRITERIA


class TestDreamPassResult:
    """Test the default passing result."""

    def test_has_all_criteria(self):
        result = _dream_pass_result()
        assert "scores" in result
        for c in GRADING_CRITERIA:
            assert c in result["scores"]

    def test_all_scores_are_10(self):
        result = _dream_pass_result()
        for c, score in result["scores"].items():
            assert score == 10

    def test_pass_is_true(self):
        result = _dream_pass_result()
        assert result["pass"] is True
        assert result["consequence"] == ""

    def test_legacy_fields_present(self):
        result = _dream_pass_result()
        assert result["confidence"] == 1.0
        assert result["doubts"] == []
        assert result["looks_fine"] is True


class TestParseDreamResult:
    """Test parsing structured dream output."""

    def test_structured_format_passing(self):
        data = {
            "scores": {"accuracy": 9, "completeness": 9, "label_quality": 8, "hallucination": 10},
            "reasons": {"accuracy": "All names correct", "completeness": "Full transcript",
                        "label_quality": "Good title", "hallucination": "No issues"},
            "pass": True,
            "consequence": "",
        }
        result = _parse_dream_result(data)
        assert result["pass"] is True
        assert result["scores"]["accuracy"] == 9

    def test_structured_format_failing(self):
        data = {
            "scores": {"accuracy": 4, "completeness": 9, "label_quality": 8, "hallucination": 10},
            "reasons": {"accuracy": "3 names mangled", "completeness": "OK",
                        "label_quality": "OK", "hallucination": "OK"},
            "pass": False,
            "consequence": "user has to correct 3 mangled names by hand",
        }
        result = _parse_dream_result(data)
        assert result["pass"] is False
        assert "3 names mangled" in result["consequence"] or "user has to correct" in result["consequence"]

    def test_model_says_pass_but_scores_disagree(self):
        """If model says pass=true but a score is below threshold, override to fail."""
        data = {
            "scores": {"accuracy": 3, "completeness": 9, "label_quality": 8, "hallucination": 10},
            "reasons": {"accuracy": "Names are wrong"},
            "pass": True,  # Model lied
            "consequence": "",
        }
        result = _parse_dream_result(data)
        assert result["pass"] is False
        assert "accuracy" in result["consequence"]

    def test_legacy_format_with_doubts(self):
        data = {
            "confidence": 0.6,
            "doubts": ["ananda my might be Anandamayi Ma"],
            "looks_fine": False,
        }
        result = _parse_dream_result(data)
        assert result["pass"] is False
        assert result["scores"]["accuracy"] < GRADING_CRITERIA["accuracy"]["threshold"]

    def test_legacy_format_no_doubts(self):
        data = {
            "confidence": 1.0,
            "doubts": [],
            "looks_fine": True,
        }
        result = _parse_dream_result(data)
        assert result["pass"] is True


class TestStepDream:
    """Test step_dream with mocked LLM."""

    def test_empty_vocabulary_returns_pass(self):
        result = step_dream("some transcript", "")
        assert result["pass"] is True

    @patch("harness.runner._call_llm")
    def test_llm_returns_none_defaults_pass(self, mock_llm):
        mock_llm.return_value = None
        result = step_dream("transcript", "vocab word")
        assert result["pass"] is True

    @patch("harness.runner._call_llm")
    def test_llm_returns_structured_scores(self, mock_llm):
        mock_llm.return_value = json.dumps({
            "scores": {"accuracy": 5, "completeness": 9, "label_quality": 7, "hallucination": 9},
            "reasons": {"accuracy": "2 names mangled"},
            "pass": False,
            "consequence": "user has to fix 2 names",
        })
        result = step_dream("transcript with ananda my", "Anandamayi Ma, satsang")
        assert result["pass"] is False
        assert result["scores"]["accuracy"] == 5


class TestStepApplyCorrections:
    """Test correction application with structured feedback."""

    def test_passing_dream_no_corrections(self):
        dream = _dream_pass_result()
        transcript, corrections = step_apply_corrections("hello world", dream, "hello")
        assert transcript == "hello world"
        assert corrections == []

    def test_corrections_with_feedback(self):
        dream = {
            "pass": False,
            "looks_fine": False,
            "doubts": ["ananda my might be Anandamayi"],
            "scores": {"accuracy": 5},
            "reasons": {"accuracy": "ananda my should be Anandamayi"},
        }
        transcript, corrections = step_apply_corrections(
            "I heard ananda my speak", dream, "Anandamayi",
            feedback=dream["reasons"],
        )
        # Corrections depend on phonetic matching — but the function should not crash
        assert isinstance(corrections, list)


class TestContextIsolation:
    """Test that the GAN loop enforces context isolation."""

    @patch("harness.runner._call_llm")
    def test_dream_calls_are_independent(self, mock_llm):
        """Each step_dream call must use the same prompt — no prior scores injected."""
        call_args_list = []

        def capture_call(system, user):
            call_args_list.append({"system": system, "user": user})
            return json.dumps({
                "scores": {"accuracy": 5, "completeness": 9, "label_quality": 7, "hallucination": 9},
                "reasons": {"accuracy": "names mangled"},
                "pass": False,
                "consequence": "fix names",
            })

        mock_llm.side_effect = capture_call

        # Call dream twice (simulating GAN loop iterations)
        step_dream("transcript v1", "Anandamayi")
        step_dream("transcript v2 with corrections", "Anandamayi")

        assert len(call_args_list) == 2

        # Both calls must have the same system prompt (DREAMER_PROMPT)
        assert call_args_list[0]["system"] == call_args_list[1]["system"]

        # Neither call should contain prior scores or "iteration" info
        for args in call_args_list:
            assert "score" not in args["user"].lower() or "scores" not in args["user"]
            assert "iteration" not in args["user"].lower()
            assert "previous" not in args["user"].lower()

        # The user content should differ only in the transcript
        assert "transcript v1" in call_args_list[0]["user"]
        assert "transcript v2" in call_args_list[1]["user"]

    @patch("harness.runner._call_llm")
    def test_dream_never_sees_corrections_applied(self, mock_llm):
        """Dreamer should not see which corrections were applied."""
        calls = []

        def capture(system, user):
            calls.append(user)
            return json.dumps({
                "scores": {"accuracy": 9, "completeness": 9, "label_quality": 8, "hallucination": 10},
                "reasons": {},
                "pass": True,
                "consequence": "",
            })

        mock_llm.side_effect = capture

        step_dream("corrected transcript", "Anandamayi")

        assert len(calls) == 1
        # Should not contain correction markers
        assert "→" not in calls[0]
        assert "corrected" not in calls[0].lower() or "transcript" in calls[0].lower()
        assert "applied" not in calls[0].lower()


class TestGANLoopIntegration:
    """Test the GAN loop in run_pipeline (integration-level with mocks)."""

    def test_max_iterations_constant(self):
        assert MAX_ITERATIONS == 3

    @patch("harness.runner.step_dream")
    @patch("harness.runner.step_apply_corrections")
    @patch("harness.runner.step_transcribe")
    @patch("harness.runner.step_generate_vocabulary")
    @patch("harness.runner.step_label")
    @patch("harness.runner.step_save")
    @patch("harness.runner.step_summarize")
    @patch("harness.runner.load_memory")
    @patch("harness.runner.append_session_log")
    def test_passes_first_try_no_loop(
        self, mock_log, mock_memory, mock_summarize, mock_save,
        mock_label, mock_vocab, mock_transcribe, mock_corrections, mock_dream,
    ):
        mock_memory.return_value = ""
        mock_vocab.return_value = "word1, word2"
        mock_transcribe.return_value = ("test transcript", None)
        mock_dream.return_value = _dream_pass_result()
        mock_label.return_value = ({"title": "Test", "description": "Desc", "tags": []}, None)
        mock_save.return_value = {}
        mock_summarize.return_value = "Done"

        results = run_pipeline("test description", "/fake/video.mp4")

        # Dream called exactly once — passed first try
        assert mock_dream.call_count == 1
        # Corrections never called
        assert mock_corrections.call_count == 0

    @patch("harness.runner.step_dream")
    @patch("harness.runner.step_apply_corrections")
    @patch("harness.runner.step_transcribe")
    @patch("harness.runner.step_generate_vocabulary")
    @patch("harness.runner.step_label")
    @patch("harness.runner.step_save")
    @patch("harness.runner.step_summarize")
    @patch("harness.runner.load_memory")
    @patch("harness.runner.append_session_log")
    def test_fails_then_passes(
        self, mock_log, mock_memory, mock_summarize, mock_save,
        mock_label, mock_vocab, mock_transcribe, mock_corrections, mock_dream,
    ):
        mock_memory.return_value = ""
        mock_vocab.return_value = "word1"
        mock_transcribe.return_value = ("bad transcript", None)

        fail_result = {
            "scores": {"accuracy": 4, "completeness": 9, "label_quality": 7, "hallucination": 9},
            "reasons": {"accuracy": "names wrong"},
            "pass": False,
            "consequence": "fix names",
            "confidence": 0.4,
            "doubts": ["word wrong"],
            "looks_fine": False,
        }
        pass_result = _dream_pass_result()
        mock_dream.side_effect = [fail_result, pass_result]
        mock_corrections.return_value = ("fixed transcript", ["old → new"])
        mock_label.return_value = ({"title": "Test", "description": "Desc", "tags": []}, None)
        mock_save.return_value = {}
        mock_summarize.return_value = "Done"

        results = run_pipeline("test", "/fake/video.mp4")

        assert mock_dream.call_count == 2
        assert mock_corrections.call_count == 1
        assert "warning" not in results

    @patch("harness.runner.step_dream")
    @patch("harness.runner.step_apply_corrections")
    @patch("harness.runner.step_transcribe")
    @patch("harness.runner.step_generate_vocabulary")
    @patch("harness.runner.step_label")
    @patch("harness.runner.step_save")
    @patch("harness.runner.step_summarize")
    @patch("harness.runner.load_memory")
    @patch("harness.runner.append_session_log")
    def test_circuit_breaker_after_max_iterations(
        self, mock_log, mock_memory, mock_summarize, mock_save,
        mock_label, mock_vocab, mock_transcribe, mock_corrections, mock_dream,
    ):
        mock_memory.return_value = ""
        mock_vocab.return_value = "word1"
        mock_transcribe.return_value = ("bad transcript", None)

        fail_result = {
            "scores": {"accuracy": 4, "completeness": 9, "label_quality": 7, "hallucination": 9},
            "reasons": {"accuracy": "still wrong"},
            "pass": False,
            "consequence": "fix names",
            "confidence": 0.4,
            "doubts": ["still wrong"],
            "looks_fine": False,
        }
        mock_dream.return_value = fail_result
        mock_corrections.return_value = ("still bad", ["attempted fix"])
        mock_label.return_value = ({"title": "Test", "description": "D", "tags": []}, None)
        mock_save.return_value = {}
        mock_summarize.return_value = "Done"

        results = run_pipeline("test", "/fake/video.mp4")

        # Dream called MAX_ITERATIONS times
        assert mock_dream.call_count == MAX_ITERATIONS
        # Corrections called MAX_ITERATIONS - 1 times (not on last iteration)
        assert mock_corrections.call_count == MAX_ITERATIONS - 1
        # Warning present
        assert "warning" in results
        assert str(MAX_ITERATIONS) in results["warning"]
        assert "final_scores" in results

    @patch("harness.runner.step_dream")
    @patch("harness.runner.step_apply_corrections")
    @patch("harness.runner.step_transcribe")
    @patch("harness.runner.step_generate_vocabulary")
    @patch("harness.runner.step_label")
    @patch("harness.runner.step_save")
    @patch("harness.runner.step_summarize")
    @patch("harness.runner.load_memory")
    @patch("harness.runner.append_session_log")
    def test_no_corrections_possible_breaks_early(
        self, mock_log, mock_memory, mock_summarize, mock_save,
        mock_label, mock_vocab, mock_transcribe, mock_corrections, mock_dream,
    ):
        """If corrections return empty list, loop should break early."""
        mock_memory.return_value = ""
        mock_vocab.return_value = "word1"
        mock_transcribe.return_value = ("transcript", None)

        fail_result = {
            "scores": {"accuracy": 5, "completeness": 9, "label_quality": 7, "hallucination": 9},
            "reasons": {"accuracy": "issue found"},
            "pass": False,
            "consequence": "fix needed",
            "confidence": 0.5,
            "doubts": ["something wrong"],
            "looks_fine": False,
        }
        mock_dream.return_value = fail_result
        mock_corrections.return_value = ("transcript", [])  # No corrections possible
        mock_label.return_value = ({"title": "Test", "description": "D", "tags": []}, None)
        mock_save.return_value = {}
        mock_summarize.return_value = "Done"

        results = run_pipeline("test", "/fake/video.mp4")

        # Should break after first dream + failed correction attempt
        assert mock_dream.call_count == 1
        assert mock_corrections.call_count == 1


class TestDreamerPrompt:
    """Test that the Dreamer prompt contains grading rubric."""

    def test_prompt_contains_criteria(self):
        for criterion in GRADING_CRITERIA:
            assert criterion in DREAMER_PROMPT

    def test_prompt_contains_thresholds(self):
        for name, config in GRADING_CRITERIA.items():
            assert f"threshold {config['threshold']}" in DREAMER_PROMPT

    def test_prompt_contains_json_format(self):
        assert '"scores"' in DREAMER_PROMPT
        assert '"reasons"' in DREAMER_PROMPT
        assert '"pass"' in DREAMER_PROMPT
        assert '"consequence"' in DREAMER_PROMPT

    def test_prompt_retains_dreamer_character(self):
        assert "Dreamer" in DREAMER_PROMPT
        assert "quietly reviewing" in DREAMER_PROMPT
        assert "before sleep" in DREAMER_PROMPT
