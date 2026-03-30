"""Tests for harness/grading.py — threshold logic, pass/fail, corrections_needed strings."""

import pytest
from harness.grading import (
    GRADING_CRITERIA,
    SCORE_MIN,
    SCORE_MAX,
    SCORE_TIERS,
    validate_scores,
    check_thresholds,
    get_tier,
    build_grading_prompt_section,
    format_failure_consequence,
    grade_to_score_data,
)


class TestValidateScores:
    """Test score validation logic."""

    def test_valid_scores_all_pass(self):
        scores = {"accuracy": 8, "completeness": 9, "label_quality": 7, "hallucination": 10}
        valid, errors = validate_scores(scores)
        assert valid is True
        assert errors == []

    def test_missing_criterion(self):
        scores = {"accuracy": 8, "completeness": 9}
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


class TestScoreTiers:
    """Test that score tiers are non-overlapping and cover 1-10."""

    def test_all_tiers_defined(self):
        assert len(SCORE_TIERS) == 5
        tier_names = [t[0] for t in SCORE_TIERS]
        assert "EXCEPTIONAL" in tier_names
        assert "ACCEPTABLE" in tier_names
        assert "QUESTIONABLE" in tier_names
        assert "FAIL" in tier_names
        assert "CRITICAL" in tier_names

    def test_tiers_non_overlapping(self):
        """Each score 1-10 belongs to exactly one tier."""
        for score in range(1, 11):
            tiers_matched = [name for name, low, high in SCORE_TIERS if low <= score <= high]
            assert len(tiers_matched) == 1, f"Score {score} matches multiple tiers: {tiers_matched}"

    def test_tiers_cover_full_range(self):
        """Every score 1-10 is covered by some tier."""
        for score in range(1, 11):
            tiers_matched = [name for name, low, high in SCORE_TIERS if low <= score <= high]
            assert len(tiers_matched) == 1, f"Score {score} has no tier"

    def test_get_tier_returns_correct_name(self):
        assert get_tier(10) == "EXCEPTIONAL"
        assert get_tier(9) == "EXCEPTIONAL"
        assert get_tier(8) == "ACCEPTABLE"
        assert get_tier(7) == "ACCEPTABLE"
        assert get_tier(6) == "QUESTIONABLE"
        assert get_tier(5) == "QUESTIONABLE"
        assert get_tier(4) == "FAIL"
        assert get_tier(3) == "FAIL"
        assert get_tier(2) == "CRITICAL"
        assert get_tier(1) == "CRITICAL"


class TestFormatFailureConsequence:
    """Test corrections_needed list generation from failures."""

    def test_no_failures_returns_list_with_empty_string(self):
        result = format_failure_consequence({})
        assert result == [""]

    def test_single_failure(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        result = format_failure_consequence(failures)
        assert len(result) == 4
        assert result[0] == ""

    def test_single_failure_with_corrections(self):
        failures = {"accuracy": {"score": 5, "threshold": 7}}
        corrections = {"accuracy": "WRONG → CORRECT at 0:47"}
        result = format_failure_consequence(failures, corrections)
        assert "WRONG → CORRECT at 0:47" in result[0]

    def test_multiple_failures(self):
        failures = {
            "accuracy": {"score": 5, "threshold": 7},
            "hallucination": {"score": 6, "threshold": 8},
        }
        result = format_failure_consequence(failures)
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
        assert '"score"' in section

    def test_contains_tier_info(self):
        section = build_grading_prompt_section()
        assert "EXCEPTIONAL" in section
        assert "ACCEPTABLE" in section
        assert "QUESTIONABLE" in section
        assert "FAIL" in section
        assert "CRITICAL" in section

    def test_contains_corrections_needed_format(self):
        section = build_grading_prompt_section()
        assert "WRONG → CORRECT at TIMESTAMP" in section or "WRONG → CORRECT at" in section

    def test_final_score_is_lowest(self):
        section = build_grading_prompt_section()
        assert "LOWEST score across all criteria" in section


class TestGradingCriteriaConfig:
    """Test the criteria configuration itself."""

    def test_all_criteria_have_required_fields(self):
        for name, config in GRADING_CRITERIA.items():
            assert "description" in config, f"{name} missing description"
            assert "threshold" in config, f"{name} missing threshold"
            assert "weight" not in config, f"{name} should not have weight field"

    def test_thresholds_in_valid_range(self):
        for name, config in GRADING_CRITERIA.items():
            assert SCORE_MIN <= config["threshold"] <= SCORE_MAX, (
                f"{name} threshold {config['threshold']} outside [{SCORE_MIN}, {SCORE_MAX}]"
            )


class TestGradeToScoreData:
    """Test conversion from grading output to scorer format."""

    def test_converts_grade_output(self):
        grades_output = {
            "scores": {"accuracy": 8, "completeness": 9, "label_quality": 7, "hallucination": 10},
            "reasons": {"accuracy": "evidence", "completeness": "evidence", "label_quality": "evidence", "hallucination": "evidence"},
            "corrections_needed": ["", "", "", ""],
            "pass": True,
            "score": 7,
        }
        result = grade_to_score_data(grades_output)
        assert result["score"] == 7
        assert result["reasons"] == {"accuracy": "evidence", "completeness": "evidence", "label_quality": "evidence", "hallucination": "evidence"}
        assert result["corrections_needed"] == ["", "", "", ""]
        assert result["pass"] is True

    def test_handles_missing_fields(self):
        grades_output = {"scores": {"accuracy": 5}}
        result = grade_to_score_data(grades_output)
        assert result["score"] == 0
        assert result["pass"] is False


class TestMangledNamesScenario:
    """Test real scenario: mangled names in transcript."""

    def test_mangled_names_fail_accuracy(self):
        scores = {
            "accuracy": 5,
            "completeness": 9,
            "label_quality": 8,
            "hallucination": 10,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "accuracy" in failures
        assert failures["accuracy"]["score"] == 5

    def test_final_score_is_lowest(self):
        scores = {
            "accuracy": 8,
            "completeness": 9,
            "label_quality": 6,
            "hallucination": 10,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert failures["label_quality"]["score"] == 6


class TestHallucinatedContentScenario:
    """Test real scenario: hallucinated content in label."""

    def test_hallucination_fails_at_7(self):
        scores = {
            "accuracy": 9,
            "completeness": 9,
            "label_quality": 8,
            "hallucination": 7,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "hallucination" in failures


class TestGenericUnknownAudioLabel:
    """Test real scenario: generic 'Unknown Audio' label."""

    def test_generic_label_fails_label_quality(self):
        scores = {
            "accuracy": 10,
            "completeness": 10,
            "label_quality": 2,
            "hallucination": 10,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert "label_quality" in failures
        assert failures["label_quality"]["score"] == 2


class TestMultipleMangledNamesScenario:
    """Test real scenario: multiple mangled names."""

    def test_multiple_failures(self):
        scores = {
            "accuracy": 4,
            "completeness": 6,
            "label_quality": 3,
            "hallucination": 5,
        }
        passed, failures = check_thresholds(scores)
        assert passed is False
        assert len(failures) == 4


class TestWhitespaceOnlyConsequenceIsRejected:
    """Verify corrections_needed is a list with empty string for pass, not whitespace."""

    def test_empty_string_for_pass(self):
        corrections = {"accuracy": ""}
        failures = {"accuracy": {"score": 10, "threshold": 7}}
        result = format_failure_consequence(failures, corrections)
        assert result[0] == ""


class TestConsequenceMentionsCorrectAction:
    """Verify corrections_needed format mentions exact wrong → correct."""

    def test_corrections_needed_has_arrow_format(self):
        section = build_grading_prompt_section()
        assert "→" in section or "->" in section