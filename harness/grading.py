"""Structured grading rubric for transcript and label quality.

Every evaluation returns scores per criterion with hard thresholds.
Below threshold on ANY criterion = FAIL.

The consequence statement prevents evaluator leniency:
"Score: 6" is abstract. "User has to correct 2 mangled names by hand" is concrete.
"""

GRADING_CRITERIA = {
    "accuracy": {
        "description": "Vocabulary words correctly transcribed, names not mangled",
        "weight": "high",
        "threshold": 7,
    },
    "completeness": {
        "description": "No dropped sentences, full transcript captured",
        "weight": "high",
        "threshold": 7,
    },
    "label_quality": {
        "description": "Title is specific and grounded in transcript, not generic",
        "weight": "medium",
        "threshold": 6,
    },
    "hallucination": {
        "description": "No names/events/details not present in audio",
        "weight": "high",
        "threshold": 8,
    },
}

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


def build_grading_prompt_section():
    """Build the grading rubric section for the Dreamer prompt.

    Returns a string to embed in the Dreamer system prompt.
    """
    lines = [
        "Rate the transcript on each criterion (1-10):",
        "",
    ]
    for name, config in GRADING_CRITERIA.items():
        lines.append(
            f"- {name} (threshold {config['threshold']}): {config['description']}"
        )
    lines.extend([
        "",
        "Respond with ONLY JSON:",
        '{',
        '  "scores": {"accuracy": N, "completeness": N, "label_quality": N, "hallucination": N},',
        '  "reasons": {"accuracy": "...", "completeness": "...", "label_quality": "...", "hallucination": "..."},',
        '  "pass": true/false,',
        '  "consequence": "" or "what the user would have to do manually"',
        '}',
        "",
        "When ANY criterion is below its threshold, set pass to false and state",
        "the concrete human consequence (e.g. 'user has to correct 2 mangled names by hand').",
        "Do NOT be lenient. State what breaks.",
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
