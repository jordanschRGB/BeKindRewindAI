"""Structured grading rubric for transcript and label quality.

Every evaluation returns scores per criterion with hard thresholds.
Below threshold on ANY criterion = FAIL.

Each criterion has EXACT mechanical thresholds and outputs corrections_needed
as a list of specific corrections, never a paragraph.
"""

# Valid score range
SCORE_MIN = 1
SCORE_MAX = 10


def validate_scores(scores):
    """Validate that scores dict has all required criteria with valid values.

    Args:
        scores: dict mapping criterion name to integer score (1-10)

    Returns:
        (valid: bool, errors: list[str])
    """
    errors = []

    for criterion in GRADING_CRITERIA:
        if criterion not in scores:
            errors.append(f"Missing criterion: {criterion}")
            continue
        val = scores[criterion]
        if not isinstance(val, (int, float)):
            errors.append(f"{criterion}: score must be numeric, got {type(val).__name__}")
        elif val < SCORE_MIN or val > SCORE_MAX:
            errors.append(f"{criterion}: score {val} outside range [{SCORE_MIN}, {SCORE_MAX}]")

    return len(errors) == 0, errors


def check_thresholds(scores):
    """Check each criterion against its threshold.

    Args:
        scores: dict mapping criterion name to integer score (1-10)

    Returns:
        (passed: bool, failures: dict mapping criterion to {"score": int, "threshold": int})
    """
    failures = {}
    for criterion, config in GRADING_CRITERIA.items():
        score = scores.get(criterion, 0)
        threshold = config["threshold"]
        if score < threshold:
            failures[criterion] = {"score": score, "threshold": threshold}

    return len(failures) == 0, failures


GRADING_CRITERIA = {
    "accuracy": {
        "weight": "high",
        "threshold": 7,
        "PASS_9_10": "Every proper noun, name, and domain term in the transcript matches the user's description EXACTLY or is spelled phonetically correctly",
        "QUESTIONABLE_6_8": "1-2 names/terms are misspelled but recoverable from context",
        "FAIL_3_5": "3+ names/terms are mangled beyond recognition OR a critical term (e.g., person's name, place) is wrong",
        "FAIL_1_2": "Transcript is mostly incomprehensible OR critical content is hallucinated",
    },
    "completeness": {
        "weight": "high",
        "threshold": 7,
        "PASS_9_10": "Full conversation captured, no sentences truncated, no silence periods over 30s omitted",
        "QUESTIONABLE_6_8": "1-2 minor truncations or omitted pauses under 10s",
        "FAIL_3_5": "Multiple sentences dropped, significant portions missing, entire sections lost",
        "FAIL_1_2": "Less than half the audio is transcribed",
    },
    "label_quality": {
        "weight": "medium",
        "threshold": 6,
        "PASS_9_10": "Title contains at least 1 specific detail from transcript (name, event, date, location)",
        "QUESTIONABLE_6_8": "Title is accurate but generic (e.g., 'Family Video' for a wedding)",
        "FAIL_3_5": "Title is wrong topic, uses content not in transcript, or is empty",
        "FAIL_1_2": "JSON malformed, title is 'Unknown Audio' or equivalent non-response",
    },
    "hallucination": {
        "weight": "high",
        "threshold": 8,
        "PASS_9_10": "No names, events, dates, or details appear in label that are absent from transcript",
        "QUESTIONABLE_6_8": "1 ambiguous detail that could exist but isn't confirmed in transcript",
        "FAIL_3_5": "1-2 hallucinated items (names, dates, events not in audio)",
        "FAIL_1_2": "3+ hallucinated items, or any significant fabricated content",
    },
}


def build_grading_prompt_section():
    """Build the grading rubric section for the Dreamer prompt.

    Returns a string to embed in the Dreamer system prompt.
    """
    lines = [
        "Rate the transcript on each criterion (1-10):",
        "",
    ]
    for name, config in GRADING_CRITERIA.items():
        lines.append(f"{name} (threshold {config['threshold']}):")
        lines.append(f"  PASS (9-10): {config['PASS_9_10']}")
        lines.append(f"  QUESTIONABLE (6-8): {config['QUESTIONABLE_6_8']}")
        lines.append(f"  FAIL (3-5): {config['FAIL_3_5']}")
        lines.append(f"  FAIL (1-2): {config['FAIL_1_2']}")
        lines.append("")

    lines.extend([
        "Respond with ONLY JSON:",
        "{",
        '  "scores": {"accuracy": N, "completeness": N, "label_quality": N, "hallucination": N},',
        '  "reasons": {"accuracy": "...", "completeness": "...", "label_quality": "...", "hallucination": "..."},',
        '  "corrections_needed": ["EXACT STRING that was wrong → EXACT STRING that should have been", ...],',
        '  "pass": true/false,',
        "}",
        "",
        "When ANY criterion is below its threshold, set pass to false and add to corrections_needed.",
        "Each correction must be: 'EXACT STRING that was wrong → EXACT STRING that should have been'.",
        "Never write a paragraph. Never write generic consequences like 'some words may be inaccurate'.",
    ])
    return "\n".join(lines)


def format_failure_consequence(failures, reasons=None):
    """Build a human-readable consequence string from failures.

    Args:
        failures: dict from check_thresholds
        reasons: optional dict of reason strings per criterion

    Returns:
        str describing what the user would have to do
    """
    if not failures:
        return ""

    parts = []
    for criterion, info in failures.items():
        reason = ""
        if reasons and criterion in reasons:
            reason = f": {reasons[criterion]}"
        parts.append(
            f"{criterion} scored {info['score']}/{info['threshold']}{reason}"
        )

    return "Quality check failed — " + "; ".join(parts)
