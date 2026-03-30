"""Tests for harness/grading.py — threshold logic, pass/fail, consequence strings."""

from unittest.mock import patch
from harness.grading import (
    GRADING_CRITERIA,
    SCORE_MIN,
    SCORE_MAX,
    validate_scores,
    check_thresholds,
    build_grading_prompt_section,
    format_failure_consequence,
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
    """Test human-readable consequence string generation."""

    def test_no_failures_empty_string(self):
        result = format_failure_consequence({})
        assert result == ""

    def test_single_failure(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        result = format_failure_consequence(failures)
        assert "accuracy" in result
        assert "5/7" in result
        assert "Quality check failed" in result

    def test_single_failure_with_reason(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        reasons = {"accuracy": "2 names mangled beyond recognition"}
        result = format_failure_consequence(failures, reasons)
        assert "2 names mangled" in result
        assert "5/7" in result

    def test_multiple_failures(self):
        failures = {
            "accuracy": {"score": 5, "threshold": 7},
            "hallucination": {"score": 6, "threshold": 8},
        }
        result = format_failure_consequence(failures)
        assert "accuracy" in result
        assert "hallucination" in result
        assert ";" in result  # Multiple failures joined with semicolons


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
        assert '"consequence"' in section

    def test_contains_consequence_instruction(self):
        section = build_grading_prompt_section()
        assert "concrete human consequence" in section.lower() or "what the user would have to do" in section.lower()


class TestGradingCriteriaConfig:
    """Test the criteria configuration itself."""

    def test_all_criteria_have_required_fields(self):
        for name, config in GRADING_CRITERIA.items():
            assert "description" in config, f"{name} missing description"
            assert "weight" in config, f"{name} missing weight"
            assert "threshold" in config, f"{name} missing threshold"

    def test_thresholds_in_valid_range(self):
        for name, config in GRADING_CRITERIA.items():
            assert SCORE_MIN <= config["threshold"] <= SCORE_MAX, (
                f"{name} threshold {config['threshold']} outside [{SCORE_MIN}, {SCORE_MAX}]"
            )

    def test_weights_are_valid(self):
        valid_weights = {"high", "medium", "low"}
        for name, config in GRADING_CRITERIA.items():
            assert config["weight"] in valid_weights, (
                f"{name} has invalid weight: {config['weight']}"
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

        self._mock_scorer(mock_call_api, '{"score": 4, "reason": "name Priya was transcribed as Pria", "consequence": "some words may be inaccurate"}')

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

        self._mock_scorer(mock_call_api, '{"score": 3, "reason": "hallucinated wedding content", "consequence": "minor issues with accuracy"}')

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

        self._mock_scorer(mock_call_api, '{"score": 2, "reason": "label is generic", "consequence": "could improve"}')

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

        self._mock_scorer(mock_call_api, '{"score": 5, "reason": "multiple names wrong", "consequence": "some accuracy issues"}')

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

        self._mock_scorer(mock_call_api, '{"score": 4, "reason": "label issues", "consequence": "   "}')

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
