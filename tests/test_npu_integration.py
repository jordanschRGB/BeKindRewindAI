"""NPU integration tests — hits the rkllama server on localhost:8081.

Requires the rkllama server to be running. Tests are skipped automatically
when the server is not reachable.

Run directly:
    python tests/test_npu_integration.py

Or via pytest (will skip if NPU is offline):
    pytest tests/test_npu_integration.py -v
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from engine.labeler import (
    NPU_BASE_URL,
    NPU_MODEL,
    _call_npu,
    _check_npu_available,
    _parse_labels,
    generate_labels,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "npu_benchmark_results.txt")


def _npu_available():
    return _check_npu_available(NPU_BASE_URL)


def _raw_generate(prompt, model=NPU_MODEL, num_predict=256):
    """Hit /api/generate directly to measure tok/s from response metadata."""
    url = f"{NPU_BASE_URL}/api/generate"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict},
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.monotonic() - t0

    eval_count = data.get("eval_count", 0)
    eval_duration_ns = data.get("eval_duration", 0)
    # rkllama reports eval_duration in milliseconds, convert → seconds
    eval_duration_s = eval_duration_ns / 1000.0 if eval_duration_ns > 0 else elapsed
    toks = eval_count / eval_duration_s if eval_duration_s > 0 else 0.0

    return data["response"], toks, eval_count, elapsed


# ---------------------------------------------------------------------------
# Fixtures / skip marker
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def require_npu():
    if not _npu_available():
        pytest.skip("rkllama NPU server not reachable at " + NPU_BASE_URL)


# ---------------------------------------------------------------------------
# Test 1: VHS labeling prompt — verify JSON parses correctly
# ---------------------------------------------------------------------------

VHS_TRANSCRIPT = (
    "Happy birthday to you, happy birthday dear Emily, happy birthday to you! "
    "Make a wish! Blow out the candles! Everybody clap! "
    "This is Emily's seventh birthday party, June 1994, Grandma's backyard."
)

VHS_LABEL_PROMPT = (
    "You are analyzing a digitized VHS tape recording. Based on the content below, "
    "generate a short title, a one-sentence description, and 3-5 relevant tags.\n\n"
    "Respond in this exact JSON format:\n"
    '{{"title": "...", "description": "...", "tags": ["...", "..."]}}\n\n'
    "Audio transcript:\n{transcript}\n\nJSON response:"
).format(transcript=VHS_TRANSCRIPT)


def test_vhs_labeling_json_parses():
    """VHS labeling prompt returns valid parseable JSON."""
    messages = [
        {"role": "system", "content": "You analyze VHS tape recordings and generate metadata. Always respond with valid JSON only, no markdown, no explanation."},
        {"role": "user", "content": VHS_LABEL_PROMPT},
    ]
    success, text, err = _call_npu(messages)
    assert success, f"NPU call failed: {err}"
    assert text is not None and len(text) > 0

    labels = _parse_labels(text)
    assert labels is not None, f"Could not parse labels from: {text!r}"
    assert "title" in labels and labels["title"]
    assert "description" in labels
    assert "tags" in labels and isinstance(labels["tags"], list)
    assert len(labels["tags"]) >= 1


# ---------------------------------------------------------------------------
# Test 2: Benchmark tok/s via /api/generate
# ---------------------------------------------------------------------------

def test_benchmark_toks():
    """Measure tok/s on VHS labeling prompt."""
    response_text, toks, eval_count, elapsed = _raw_generate(VHS_LABEL_PROMPT, num_predict=200)
    # Sanity check: we got something back
    assert len(response_text) > 0
    # Report (test always passes as long as we get a response)
    print(f"\n[NPU benchmark] model={NPU_MODEL} tokens={eval_count} tok/s={toks:.1f} elapsed={elapsed:.2f}s")


# ---------------------------------------------------------------------------
# Test 3: Vocabulary priming prompt
# ---------------------------------------------------------------------------

VOCAB_PRIMING_PROMPT = (
    "You are a metadata expert for a VHS digitization archive. "
    "The following vocabulary terms are commonly used in this collection:\n"
    "- Birthday parties, holidays, graduations, weddings\n"
    "- Family gatherings, vacations, school events\n"
    "- Home movies, camcorder footage, VHS tape\n\n"
    "Using this vocabulary, analyze the following transcript and generate a title, "
    "description, and tags in JSON format:\n"
    '{{"title": "...", "description": "...", "tags": ["...", "..."]}}\n\n'
    "Transcript: Kids running around in the snow, building a snowman, "
    "throwing snowballs. Someone shouts 'Merry Christmas 1989!'\n\n"
    "JSON:"
)


def test_vocabulary_priming():
    """Vocabulary-primed prompt produces valid labels."""
    messages = [
        {"role": "system", "content": "You analyze VHS tape recordings. Respond with valid JSON only."},
        {"role": "user", "content": VOCAB_PRIMING_PROMPT},
    ]
    success, text, err = _call_npu(messages)
    assert success, f"NPU call failed: {err}"

    labels = _parse_labels(text)
    assert labels is not None, f"Could not parse labels from vocab priming: {text!r}"
    assert labels["title"]
    assert labels["tags"]


# ---------------------------------------------------------------------------
# Test 4: Dreamer-style doubt detection
# ---------------------------------------------------------------------------

DOUBT_PROMPT = (
    "You are a quality-control assistant for a VHS digitization archive. "
    "Evaluate the following AI-generated metadata and flag any uncertain or "
    "potentially incorrect labels. Respond in JSON:\n"
    '{{"confidence": "high|medium|low", "doubts": ["...", "..."], "reason": "..."}}\n\n'
    "Metadata to review:\n"
    '{"title": "Summer BBQ 1987", "description": "Family barbecue in the backyard.", '
    '"tags": ["barbecue", "summer", "1987", "family"]}\n\n'
    "Transcript used: 'Pass me the ketchup. Is that the Hendersons? Look at that fire! "
    "Uncle Bob always burns the hot dogs. What year is this, eighty-six or eighty-seven?'\n\n"
    "JSON evaluation:"
)


def test_dreamer_doubt_detection():
    """Dreamer-style doubt detection returns structured evaluation."""
    messages = [
        {"role": "system", "content": "You are a quality-control assistant. Respond with valid JSON only."},
        {"role": "user", "content": DOUBT_PROMPT},
    ]
    success, text, err = _call_npu(messages)
    assert success, f"NPU call failed: {err}"
    assert text is not None

    # Try to extract JSON
    text_clean = text.strip()
    if text_clean.startswith("```"):
        lines = text_clean.split("\n")
        text_clean = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    start = text_clean.find("{")
    end = text_clean.rfind("}") + 1
    assert start >= 0 and end > start, f"No JSON found in: {text!r}"

    data = json.loads(text_clean[start:end])
    assert "confidence" in data or "doubts" in data or "reason" in data, \
        f"Expected doubt keys not found in: {data}"


# ---------------------------------------------------------------------------
# Test 5: Full generate_labels pipeline uses NPU
# ---------------------------------------------------------------------------

def test_generate_labels_uses_npu():
    """generate_labels() succeeds end-to-end using the NPU backend."""
    success, labels, err = generate_labels(transcript=VHS_TRANSCRIPT)
    assert success, f"generate_labels failed: {err}"
    assert labels is not None
    assert labels["title"]


# ---------------------------------------------------------------------------
# Benchmark report writer (runs after all tests)
# ---------------------------------------------------------------------------

def _write_benchmark_report():
    """Write benchmark results to npu_benchmark_results.txt."""
    if not _npu_available():
        return

    lines = [
        f"NPU Benchmark Results",
        f"=====================",
        f"Date: {datetime.now().isoformat()}",
        f"Server: {NPU_BASE_URL}",
        f"Model: {NPU_MODEL}",
        "",
    ]

    test_cases = [
        ("VHS labeling prompt", VHS_LABEL_PROMPT, 200),
        ("Vocabulary priming prompt", VOCAB_PRIMING_PROMPT, 150),
        ("Dreamer doubt detection prompt", DOUBT_PROMPT, 150),
    ]

    for name, prompt, num_predict in test_cases:
        try:
            response_text, toks, eval_count, elapsed = _raw_generate(prompt, num_predict=num_predict)
            labels = _parse_labels(response_text)
            json_ok = "YES" if labels else "NO (raw response below)"
            lines.append(f"[{name}]")
            lines.append(f"  tokens generated : {eval_count}")
            lines.append(f"  tok/s            : {toks:.1f}")
            lines.append(f"  wall time        : {elapsed:.2f}s")
            lines.append(f"  JSON parseable   : {json_ok}")
            if not labels:
                lines.append(f"  raw              : {response_text[:200]!r}")
            lines.append("")
        except Exception as e:
            lines.append(f"[{name}] FAILED: {e}")
            lines.append("")

    with open(RESULTS_FILE, "w") as f:
        f.write("\n".join(lines))
    print(f"\nBenchmark results written to {RESULTS_FILE}")


# ---------------------------------------------------------------------------
# Direct run entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not _npu_available():
        print(f"ERROR: rkllama server not reachable at {NPU_BASE_URL}")
        sys.exit(1)

    print(f"NPU server available at {NPU_BASE_URL}")
    print(f"Model: {NPU_MODEL}\n")

    # Run benchmark and write report
    _write_benchmark_report()

    # Run all tests manually
    import traceback
    tests = [
        test_vhs_labeling_json_parses,
        test_benchmark_toks,
        test_vocabulary_priming,
        test_dreamer_doubt_detection,
        test_generate_labels_uses_npu,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    if os.path.exists(RESULTS_FILE):
        print(f"\n--- {RESULTS_FILE} ---")
        with open(RESULTS_FILE) as f:
            print(f.read())

    sys.exit(0 if failed == 0 else 1)
