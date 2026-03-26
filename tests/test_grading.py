"""Tests for harness/grading.py — threshold logic, pass/fail, consequence strings."""

import pytest
from harness.grading import (
    GRADING_CRITERIA,
    SCORE_MIN,
    SCORE_MAX,
    validate_scores,
    check_thresholds,
    build_grading_prompt_section,
    format_failure_consequence,
)


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
