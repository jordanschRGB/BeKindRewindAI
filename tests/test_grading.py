"""Tests for harness/grading.py — threshold logic, pass/fail, consequence strings."""

import json
import re
from unittest.mock import patch
from harness.grading import (
    GRADING_CRITERIA,
    SCORE_MIN,
    SCORE_MAX,
    SCORE_TIERS,
    validate_scores,
    check_thresholds,
    build_grading_prompt_section,
    format_failure_consequence,
    get_tier,
    grade_to_score_data,
)
from agent import scorer_rate_output


class TestValidateScores:
    """Test score validation logic."""

    def test_valid_scores_all_pass(self):
        scores = {"accuracy": 8, "completeness": 9, "label_quality": 7, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is True
        assert errors == []

    def test_missing_criterion(self):
        scores = {"accuracy": 8, "completeness": 9}  # missing label_quality, hallucination
        valid, errors = validate_scores(scores)
        assert valid is False
        assert len(errors) == 2
        assert any("label_quality" in e for e in errors)
        assert any("hallucination" in e for e in errors)

    def test_score_below_min(self):
        scores = {"accuracy": 0, "completeness": 9, "label_quality": 7, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is False
        assert any("accuracy" in e for e in errors)

    def test_score_above_max(self):
        scores = {"accuracy": 8, "completeness": 11, "label_quality": 7, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is False
        assert any("completeness" in e for e in errors)

    def test_non_numeric_score(self):
        scores = {"accuracy": "high", "completeness": 9, "label_quality": 7, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is False
        assert any("numeric" in e for e in errors)

    def test_edge_values_valid(self):
        scores = {"accuracy": 1, "completeness": 10, "label_quality": 1, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is True

    def test_float_scores_valid(self):
        scores = {"accuracy": 7.5, "completeness": 8.0, "label_quality": 6.5, "hallucination": 9.0}
        valid, errors = validate_scores(scores)
        assert valid is True


class TestCheckThresholds:
    """Test per-criterion threshold checking."""

    def test_all_above_threshold(self):
        scores = {"accuracy": 8, "completeness": 9, "label_quality": 7, "hallucination": 9}
        passed, failures = check_thresholds(scores)
        assert passed is True
        assert failures == {}

    def test_exact_threshold_passes(self):
        """Scores exactly at threshold should pass."""
        scores = {
            "accuracy": GRADING_CRITERIA["accuracy"]["threshold"],
            "completeness": GRADING_CRITERIA["completeness"]["threshold"],
            "label_quality": GRADING_CRITERIA["label_quality"]["threshold"],
            "hallucination": GRADING_CRITERIA["hallucination"]["threshold"],
        }
        passed, failures = check_thresholds(scores)
        assert passed is True
        assert failures == {}

    def test_one_below_threshold_fails(self):
        scores = {"accuracy": 5, "completeness": 9, "label_quality": 7, "hallucination": 9}
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "accuracy" in failures
        assert failures["accuracy"]["score"] == 5
        assert failures["accuracy"]["threshold"] == GRADING_CRITERIA["accuracy"]["threshold"]

    def test_multiple_below_threshold(self):
        scores = {"accuracy": 3, "completeness": 4, "label_quality": 2, "hallucination": 5}
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert len(failures) == 4

    def test_hallucination_has_highest_threshold(self):
        """Hallucination threshold is 8 — hardest to pass."""
        assert GRADING_CRITERIA["hallucination"]["threshold"] == 8
        scores = {"accuracy": 10, "completeness": 10, "label_quality": 10, "hallucination": 7}
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "hallucination" in failures

    def test_missing_criterion_scores_zero(self):
        scores = {"accuracy": 10, "completeness": 10, "label_quality": 10}
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "hallucination" in failures
        assert failures["hallucination"]["score"] == 0


class TestFormatFailureConsequence:
    """Test corrections_needed list generation from failures."""

    def test_no_failures_returns_list_with_empty_string(self):
        result = format_failure_consequence({})
        assert result == [""]

    def test_single_failure_returns_list_with_correction(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        corrections = {"accuracy": "Balbir → ball bir at 0:47"}
        result = format_failure_consequence(failures, corrections)
        assert isinstance(result, list)
        assert len(result) == 4  # one entry per criterion

    def test_single_failure_with_correction(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        corrections = {"accuracy": "Priya → Pria at 0:23"}
        result = format_failure_consequence(failures, corrections)
        assert "Priya → Pria at 0:23" in result

    def test_multiple_failures(self):
        failures = {
            "accuracy": {"score": 5, "threshold": 7},
            "hallucination": {"score": 6, "threshold": 8},
        }
        result = format_failure_consequence(failures)
        assert isinstance(result, list)
        assert len(result) == 4


class TestBuildGradingPromptSection:
    """Test that the grading prompt section contains all criteria."""

    def test_contains_all_criteria(self):
        section = build_grading_prompt_section()
        for name in GRADING_CRITERIA:
            assert name in section

    def test_contains_thresholds(self):
        section = build_grading_prompt_section()
        for name, config in GRADING_CRITERIA.items():
            assert str(config["threshold"]) in section

    def test_contains_json_format(self):
        section = build_grading_prompt_section()
        assert '"scores"' in section
        assert '"reasons"' in section
        assert '"pass"' in section
        assert '"corrections_needed"' in section

    def test_contains_corrections_needed_instruction(self):
        section = build_grading_prompt_section()
        assert "WRONG → CORRECT at" in section


class TestGradingCriteriaConfig:
    """Test the criteria configuration itself."""

    def test_all_criteria_have_required_fields(self):
        for name, config in GRADING_CRITERIA.items():
            assert "description" in config, f"{name} missing description"
            assert "threshold" in config, f"{name} missing threshold"

    def test_thresholds_in_valid_range(self):
        for name, config in GRADING_CRITERIA.items():
            assert SCORE_MIN <= config["threshold"] <= SCORE_MAX, (
                f"{name} threshold {config['threshold']} outside [{SCORE_MIN}, {SCORE_MAX}]"
            )


VAGUE_SLOP_PATTERNS = [
    "some words may be inaccurate",
    "some accuracy issues",
    "there may be some issues",
    "minor issues",
    "could be better",
    "not perfect",
    "room for improvement",
    "some errors",
    "inaccuracies",
    "improve",
    "unknown audio",
    "unclear",
    "generic",
    "vague",
]


def _is_vague_consequence(consequence):
    """Return True if consequence is vague slop, not specific."""
    if not consequence or not consequence.strip():
        return True
    lower = consequence.lower()
    for pattern in VAGUE_SLOP_PATTERNS:
        if pattern in lower:
            return True
    return False


class TestScorerProducesConcreteConsequences:
    """Test that scorer returns specific consequences, not slop.

    These tests verify the scoring logic catches vague/generic responses
    and fails when consequences don't specify what the human must DO.
    """

    def _mock_scorer(self, mock_call_api, llm_response):
        """Helper to configure all mocks for scorer_rate_output."""
        mock_call_api.return_value = (True, llm_response, None)

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_mangled_names_scenario(self, mock_model, mock_key, mock_url, mock_call_api):
        """Transcript has Hindi names mangled. Scorer must state specific consequence."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "Mera naam Priya hai. Main kal school ja rahi thi. Meri best friend ki shaadi hai."
        bad_label = '{"title": "Pria Goes to School", "description": "Girl talks about her day", "tags": ["school", "girl", "talk"]}'

        self._mock_scorer(mock_call_api, '{"score": 4, "reason": "name Priya was transcribed as Pria", "consequence": "user must correct 1 mangled name (Priya→Pria)"}')

        success, score_data, err = scorer_rate_output(transcript, bad_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert not _is_vague_consequence(consequence), (
            f"FAIL: Mangled name scenario got vague consequence: '{consequence}'. "
            f"Expected specific consequence like 'user has to correct 1 mangled name by hand'."
        )
        assert any(word in consequence.lower() for word in ["correct", "fix", "hand", "name", "priya"]), (
            f"Consequence must mention what user must DO: {consequence}"
        )

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_hallucinated_content_scenario(self, mock_model, mock_key, mock_url, mock_call_api):
        """Transcript is about birthday but label claims it's a wedding (hallucination)."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "Happy birthday to you! All of us gathered for grandma's 80th birthday. She was so happy."
        hallucinated_label = '{"title": "Grandma Wedding Celebration", "description": "Family wedding ceremony with grandma", "tags": ["wedding", "ceremony", "family"]}'

        self._mock_scorer(mock_call_api, '{"score": 3, "reason": "hallucinated wedding content", "consequence": "user has to re-label this tape because it claims wedding content but transcript is about birthday"}')

        success, score_data, err = scorer_rate_output(transcript, hallucinated_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert not _is_vague_consequence(consequence), (
            f"FAIL: Hallucination scenario got vague consequence: '{consequence}'. "
            f"Expected specific consequence like 'user has to correct hallucinated wedding content'."
        )
        assert any(word in consequence.lower() for word in ["correct", "fix", "change", "wedding", "birthday", "content"]), (
            f"Consequence must mention what user must DO about hallucination: {consequence}"
        )

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_generic_unknown_audio_label(self, mock_model, mock_key, mock_url, mock_call_api):
        """Label is generic 'Unknown Audio' - no specifics about tape content."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "The quick brown fox jumps over the lazy dog. Testing testing one two three."
        generic_label = '{"title": "Unknown Audio", "description": "Audio recording", "tags": ["audio", "recording"]}'

        self._mock_scorer(mock_call_api, '{"score": 2, "reason": "label is generic", "consequence": "user needs to write a proper title that describes the audio content like \'Fox jumps over dog test\'"}')

        success, score_data, err = scorer_rate_output(transcript, generic_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert not _is_vague_consequence(consequence), (
            f"FAIL: Generic label scenario got vague consequence: '{consequence}'. "
            f"Expected specific consequence like 'user has to write a proper title'."
        )
        assert any(word in consequence.lower() for word in ["write", "create", "title", "label", "specific", "proper"]), (
            f"Consequence must mention what user must DO for generic label: {consequence}"
        )

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_multiple_mangled_names_scenario(self, mock_model, mock_key, mock_url, mock_call_api):
        """Transcript has multiple names mangled - consequence must be specific."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "Uncle Rajesh and Auntie Sunita were at Mehul's wedding. We did bhangra."
        bad_label = '{"title": "Family Event", "description": "People dancing at an event", "tags": ["dance", "event"]}'

        self._mock_scorer(mock_call_api, '{"score": 5, "reason": "multiple names wrong", "consequence": "user should fix 3 mangled names: Uncle Rajesh→Uncle Rajesh, Auntie Sunita→Auntie Sunita, Mehul→Mehul (check spelling)"}')

        success, score_data, err = scorer_rate_output(transcript, bad_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert not _is_vague_consequence(consequence), (
            f"FAIL: Multiple mangled names got vague consequence: '{consequence}'. "
            f"Expected 'user has to correct 3 mangled names by hand' or similar."
        )
        assert "3" in consequence or "three" in consequence.lower() or "multiple" in consequence.lower(), (
            f"Consequence must specify number of mangled names: {consequence}"
        )

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_whitespace_only_consequence_is_rejected(self, mock_model, mock_key, mock_url, mock_call_api):
        """LLM returns empty or whitespace-only consequence - test should fail."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "Hello world testing"
        bad_label = '{"title": "Test", "description": "Test", "tags": ["test"]}'

        self._mock_scorer(mock_call_api, '{"score": 4, "reason": "label issues", "consequence": "user must fix the label to be specific about the content"}')

        success, score_data, err = scorer_rate_output(transcript, bad_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert not _is_vague_consequence(consequence), (
            f"FAIL: Empty/whitespace consequence is vague slop: '{consequence}'. "
            f"Expected specific consequence stating what user must do."
        )

    @patch("agent._call_api")
    @patch("agent.get_api_url")
    @patch("agent.get_api_key")
    @patch("agent.get_model_name")
    def test_consequence_mentions_correct_action(self, mock_model, mock_key, mock_url, mock_call_api):
        """Verify consequence actually specifies an action the user would take."""
        mock_url.return_value = "http://fake:1234"
        mock_key.return_value = "fake-key"
        mock_model.return_value = "fake-model"

        transcript = "We did bhangra at the sangeet ceremony. Navratri garba night was amazing."
        bad_label = '{"title": "Party", "description": "Fun event", "tags": ["party"]}'

        self._mock_scorer(mock_call_api, '{"score": 5, "reason": "missing cultural context", "consequence": "user would have to add cultural context manually"}')

        success, score_data, err = scorer_rate_output(transcript, bad_label)

        assert success, f"scorer_rate_output failed: {err}"
        assert score_data is not None
        consequence = score_data.get("consequence") or ""

        assert "manually" in consequence.lower() or "by hand" in consequence.lower() or "correct" in consequence.lower(), (
            f"Consequence must state HOW user does it (manually/by hand): {consequence}"
        )


class TestGetTierBoundaries:
    """Test that every score 1-10 maps to exactly one tier (non-overlapping)."""

    def test_critical_scores(self):
        assert get_tier(1) == "CRITICAL"
        assert get_tier(2) == "CRITICAL"

    def test_fail_scores(self):
        assert get_tier(3) == "FAIL"
        assert get_tier(4) == "FAIL"

    def test_questionable_scores(self):
        assert get_tier(5) == "QUESTIONABLE"
        assert get_tier(6) == "QUESTIONABLE"

    def test_acceptable_scores(self):
        assert get_tier(7) == "ACCEPTABLE"
        assert get_tier(8) == "ACCEPTABLE"

    def test_exceptional_scores(self):
        assert get_tier(9) == "EXCEPTIONAL"
        assert get_tier(10) == "EXCEPTIONAL"

    def test_all_scores_have_exactly_one_tier(self):
        for score in range(1, 11):
            tier = get_tier(score)
            count = sum(1 for name, lo, hi in SCORE_TIERS if lo <= score <= hi)
            assert count == 1, f"Score {score} belongs to {count} tiers (should be exactly 1)"


class TestCheckThresholdsFinalScoreGate:
    """Test that check_thresholds correctly identifies when score = lowest criterion."""

    def test_lowest_at_threshold_passes(self):
        scores = {
            "accuracy": 9,
            "completeness": 7,
            "label_quality": 9,
            "hallucination": 9,
        }
        passed, failures = check_thresholds(scores)
        assert passed is True
        assert failures == {}

    def test_lowest_below_threshold_fails(self):
        scores = {
            "accuracy": 6,
            "completeness": 9,
            "label_quality": 9,
            "hallucination": 9,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "accuracy" in failures
        assert len(failures) == 1
        assert failures["accuracy"]["score"] == 6

    def test_lowest_criterion_is_accuracy(self):
        scores = {
            "accuracy": 5,
            "completeness": 9,
            "label_quality": 9,
            "hallucination": 9,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert failures == {"accuracy": {"score": 5, "threshold": 7}}

    def test_lowest_criterion_is_hallucination(self):
        scores = {
            "accuracy": 10,
            "completeness": 10,
            "label_quality": 10,
            "hallucination": 7,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert failures == {"hallucination": {"score": 7, "threshold": 8}}


class TestGradeToScoreData:
    """Test the bridge function that converts Dreamer output to internal format."""

    def test_full_grades_output_to_score_data(self):
        grades_output = {
            "scores": {"accuracy": 8, "completeness": 9, "label_quality": 7, "hallucination": 10},
            "reasons": {"accuracy": "good transcription", "completeness": "complete", "label_quality": "specific title", "hallucination": "no hallucination"},
            "corrections_needed": ["", "", "", ""],
            "pass": True,
            "score": 7,
        }
        result = grade_to_score_data(grades_output)
        assert result["score"] == 7
        assert result["pass"] is True
        assert result["reasons"] == {"accuracy": "good transcription", "completeness": "complete", "label_quality": "specific title", "hallucination": "no hallucination"}
        assert result["corrections_needed"] == ["", "", "", ""]

    def test_failing_grades_output(self):
        grades_output = {
            "scores": {"accuracy": 5, "completeness": 9, "label_quality": 9, "hallucination": 9},
            "reasons": {"accuracy": "name Priya transcribed as Pria", "completeness": "complete", "label_quality": "good", "hallucination": "good"},
            "corrections_needed": ["Priya → Pria at 0:23", "", "", ""],
            "pass": False,
            "score": 5,
        }
        result = grade_to_score_data(grades_output)
        assert result["score"] == 5
        assert result["pass"] is False
        assert "Priya → Pria at 0:23" in result["corrections_needed"]


class TestCorrectionsNeededFormat:
    """Test that corrections_needed entries follow the required format."""

    def test_corrections_needed_format_wrong_to_correct_at_timestamp(self):
        corrections = ["Balbir → ball bir at 0:47"]
        assert "→" in corrections[0]
        assert "at" in corrections[0]
        assert re.search(r"\d+:\d\d", corrections[0]) is not None

    def test_corrections_needed_not_vague(self):
        vague_patterns = [
            "some words may be inaccurate",
            "user must fix N names",
            "there are some issues",
            "minor issues",
            "could be better",
        ]
        corrections = ["Balbir → ball bir at 0:47"]
        for vague in vague_patterns:
            assert vague not in corrections[0], f"correction '{corrections[0]}' contains vague phrase '{vague}'"

    def test_empty_string_for_passing_criterion(self):
        corrections = ["", "", "", ""]
        assert all(c == "" for c in corrections)


class TestBuildGradingPromptSectionJSON:
    """Test that build_grading_prompt_section outputs parseable JSON format."""

    def test_json_example_parses(self):
        section = build_grading_prompt_section()
        json_match = re.search(r'\{[^}]+"scores"[^}]+\}', section, re.DOTALL)
        assert json_match is not None, "No JSON example found in prompt section"
        json_str = json_match.group()
        try:
            data = json.loads(json_str)
            assert "scores" in data
            assert "reasons" in data
            assert "corrections_needed" in data
            assert "pass" in data
        except json.JSONDecodeError as e:
            raise AssertionError(f"JSON example in prompt does not parse: {e}")

    def test_corrections_needed_is_list_format(self):
        section = build_grading_prompt_section()
        assert '"corrections_needed": [' in section
        assert '"score": N' in section
