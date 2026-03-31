"""Structured grading rubric for transcript and label quality.

Every evaluation returns scores per criterion with hard thresholds.
Below threshold on ANY criterion = FAIL.

The corrections_needed statement prevents evaluator leniency:
"Score: 6" is abstract. "User has to correct 2 mangled names by hand" is concrete.
"""

GRADING_CRITERIA = {
    "accuracy": {
        "description": "Vocabulary words correctly transcribed, names not mangled",
        "threshold": 7,
    },
    "completeness": {
        "description": "No dropped sentences, full transcript captured",
        "threshold": 7,
    },
    "label_quality": {
        "description": "Title is specific and grounded in transcript, not generic",
        "threshold": 6,
    },
    "hallucination": {
        "description": "No names/events/details not present in audio",
        "threshold": 8,
    },
}

SCORE_TIERS = [
    ("EXCEPTIONAL", 9, 10),
    ("ACCEPTABLE", 7, 8),
    ("QUESTIONABLE", 5, 6),
    ("FAIL", 3, 4),
    ("CRITICAL", 1, 2),
]

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
    tier_desc = ", ".join(f"{name}({l}-{h})" for name, l, h in SCORE_TIERS)
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
        f"Score tiers (each score 1-10 belongs to exactly one tier): {tier_desc}",
        "",
        "Final score = LOWEST score across all criteria.",
        "",
        "Respond with ONLY JSON:",
        "{",
        '  "scores": {"accuracy": N, "completeness": N, "label_quality": N, "hallucination": N},',
        '  "reasons": {"accuracy": "exact transcript evidence string", "completeness": "exact transcript evidence string", "label_quality": "exact transcript evidence string", "hallucination": "exact transcript evidence string"},',
        '  "corrections_needed": ["exact wrong → exact correct at timestamp", ...],',
        '  "pass": true/false,',
        '  "score": N',
        "}",
        "",
        "corrections_needed format: each entry is 'WRONG → CORRECT at TIMESTAMP'.",
        "If a criterion passes, its corrections_needed entry is '' (empty string).",
        "If all criteria pass, corrections_needed is [''].",
        "When ANY criterion fails, state what the user must fix:",
        "- For accuracy: 'transcript says WRONG → CORRECT at 0:47'",
        "- For completeness: 'missing transcript from TIMESTAMP: [exact missing phrase]'",
        "- For label_quality: 'title says WRONG → CORRECT at 0:00'",
        "- For hallucination: 'label contains WRONG → but transcript says CORRECT at TIMESTAMP'",
    ])
    return "\n".join(lines)


def get_tier(score):
    """Return the tier name for a score.

    Tiers are non-overlapping and cover 1-10:
    - EXCEPTIONAL: 9-10
    - ACCEPTABLE: 7-8
    - QUESTIONABLE: 5-6
    - FAIL: 3-4
    - CRITICAL: 1-2
    """
    for name, low, high in SCORE_TIERS:
        if low <= score <= high:
            return name
    return "CRITICAL"


def format_failure_consequence(failures, corrections_needed=None):
    """Build corrections_needed list from failures.

    Args:
        failures: dict from check_thresholds
        corrections_needed: optional dict of correction strings per criterion

    Returns:
        list of correction strings
    """
    if not failures:
        return [""]

    result = []
    for criterion in GRADING_CRITERIA:
        if criterion in failures:
            info = failures[criterion]
            correction = ""
            if corrections_needed and criterion in corrections_needed:
                correction = corrections_needed[criterion]
            tier = get_tier(info["score"])
            result.append(f"{correction}")
        else:
            result.append("")
    return result


def grade_to_score_data(grades_output):
    """Convert grading.py output to SCORER_SYSTEM format.

    Args:
        grades_output: dict with keys: scores, reasons, corrections_needed, pass, score

    Returns:
        dict with keys: score, reason, corrections_needed, pass
    """
    return {
        "score": grades_output.get("score", 0),
        "reason": grades_output.get("reasons", {}),
        "corrections_needed": grades_output.get("corrections_needed", []),
        "pass": grades_output.get("pass", False),
    }
