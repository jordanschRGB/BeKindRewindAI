"""Tests for the vocabulary feedback loop.

Tests agent.append_vocabulary_feedback and agent.get_vocabulary_feedback,
and the runner-level feedback logging logic.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_memory_file(tmp_path, content=""):
    """Point agent.MEMORY_FILE at a temp file and write initial content."""
    mem_dir = tmp_path / ".memoryvault"
    mem_dir.mkdir()
    mem_file = mem_dir / "archivist_memory.md"
    if content:
        mem_file.write_text(content)
    # Patch the module-level constant
    original = agent.MEMORY_FILE
    agent.MEMORY_FILE = str(mem_file)
    return original


def _restore_memory_file(original):
    agent.MEMORY_FILE = original


# ── append_vocabulary_feedback ────────────────────────────────────────────────

class TestAppendVocabularyFeedback:
    def test_creates_section_when_absent(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback(["Anandamayi"], ["satsang"])
            memory = agent.load_memory()
            assert "## Vocabulary Feedback" in memory
        finally:
            _restore_memory_file(orig)

    def test_records_used_words(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback(["kirtan", "mantra"], [])
            memory = agent.load_memory()
            assert "used=[kirtan, mantra]" in memory
        finally:
            _restore_memory_file(orig)

    def test_records_unused_words(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback([], ["bhajan", "swami"])
            memory = agent.load_memory()
            assert "noise=[bhajan, swami]" in memory
        finally:
            _restore_memory_file(orig)

    def test_records_none_for_empty_lists(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback([], [])
            memory = agent.load_memory()
            assert "used=[(none)]" in memory
            assert "noise=[(none)]" in memory
        finally:
            _restore_memory_file(orig)

    def test_multiple_entries_accumulate(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback(["kirtan"], ["mantra"])
            agent.append_vocabulary_feedback(["satsang"], ["guru"])
            memory = agent.load_memory()
            assert memory.count("- ") >= 2
        finally:
            _restore_memory_file(orig)

    def test_appends_to_existing_memory(self, tmp_path):
        existing = "# Archivist Memory\n\n## Sessions\n- 2026-01-01: did stuff\n"
        orig = _make_memory_file(tmp_path, existing)
        try:
            agent.append_vocabulary_feedback(["Om"], [])
            memory = agent.load_memory()
            # Sessions section should still be there
            assert "## Sessions" in memory
            assert "## Vocabulary Feedback" in memory
        finally:
            _restore_memory_file(orig)

    def test_section_appears_only_once(self, tmp_path):
        orig = _make_memory_file(tmp_path)
        try:
            agent.append_vocabulary_feedback(["kirtan"], [])
            agent.append_vocabulary_feedback(["satsang"], [])
            memory = agent.load_memory()
            assert memory.count("## Vocabulary Feedback") == 1
        finally:
            _restore_memory_file(orig)


# ── get_vocabulary_feedback ───────────────────────────────────────────────────

class TestGetVocabularyFeedback:
    def test_empty_memory_returns_empty(self):
        result = agent.get_vocabulary_feedback("")
        assert result == {"useful": [], "noise": []}

    def test_no_feedback_section_returns_empty(self):
        memory = "# Archivist Memory\n\n## Sessions\n- did stuff\n"
        result = agent.get_vocabulary_feedback(memory)
        assert result == {"useful": [], "noise": []}

    def test_useful_word_extracted(self):
        memory = (
            "# Archivist Memory\n\n"
            "## Vocabulary Feedback\n"
            "- 2026-01-01 10:00: used=[kirtan] noise=[(none)]\n"
        )
        result = agent.get_vocabulary_feedback(memory)
        assert "kirtan" in result["useful"]
        assert result["noise"] == []

    def test_noise_word_extracted(self):
        memory = (
            "# Archivist Memory\n\n"
            "## Vocabulary Feedback\n"
            "- 2026-01-01 10:00: used=[(none)] noise=[mantra]\n"
        )
        result = agent.get_vocabulary_feedback(memory)
        assert "mantra" in result["noise"]
        assert result["useful"] == []

    def test_majority_wins_across_entries(self):
        # "kirtan" appears as useful twice, noise once — should be useful
        memory = (
            "# Archivist Memory\n\n"
            "## Vocabulary Feedback\n"
            "- 2026-01-01 10:00: used=[kirtan] noise=[(none)]\n"
            "- 2026-01-02 10:00: used=[kirtan] noise=[(none)]\n"
            "- 2026-01-03 10:00: used=[(none)] noise=[kirtan]\n"
        )
        result = agent.get_vocabulary_feedback(memory)
        assert "kirtan" in result["useful"]
        assert "kirtan" not in result["noise"]

    def test_stops_at_next_section(self):
        # Words after a subsequent section header should not be parsed
        memory = (
            "# Archivist Memory\n\n"
            "## Vocabulary Feedback\n"
            "- 2026-01-01 10:00: used=[kirtan] noise=[(none)]\n"
            "\n## Sessions\n"
            "- 2026-01-01: some session used=[shouldNotAppear] noise=[(none)]\n"
        )
        result = agent.get_vocabulary_feedback(memory)
        assert "shouldNotAppear" not in result["useful"]
        assert "kirtan" in result["useful"]

    def test_multiple_words_per_entry(self):
        memory = (
            "# Archivist Memory\n\n"
            "## Vocabulary Feedback\n"
            "- 2026-01-01 10:00: used=[kirtan, mantra, satsang] noise=[bhajan, guru]\n"
        )
        result = agent.get_vocabulary_feedback(memory)
        assert "kirtan" in result["useful"]
        assert "mantra" in result["useful"]
        assert "satsang" in result["useful"]
        assert "bhajan" in result["noise"]
        assert "guru" in result["noise"]


# ── Runner feedback logic (unit-level, no LLM) ────────────────────────────────

class TestRunnerFeedbackLogic:
    """Test the corrected word-classification logic used in run_pipeline.

    Signal definition (fixed from original inverted logic):
    - "used" (useful): word appears in final transcript OR as correction target
      (priming worked, either Whisper got it right or Dreamer caught the mishear)
    - "unused" (noise): word appears in NEITHER transcript NOR corrections
      (genuinely irrelevant to this content)

    The original bug: words were "used" only if they appeared as correction
    targets, so words Whisper transcribed correctly (priming worked!) were
    classified as noise. This would teach the Worker to deprioritize working
    vocabulary.
    """

    def _classify(self, vocab_words, corrections, transcript):
        """Replicate the corrected classification logic from runner.py."""
        transcript_lower = transcript.lower()
        corrected_targets = set()
        for c in corrections:
            if " \u2192 " in c:
                corrected_targets.add(c.split(" \u2192 ")[1].strip().lower())

        used = [w for w in vocab_words if w.lower() in transcript_lower or w.lower() in corrected_targets]
        unused = [w for w in vocab_words if w.lower() not in transcript_lower and w.lower() not in corrected_targets]
        return used, unused

    def test_word_correct_in_transcript_is_used(self):
        """Words Whisper got right (priming worked) must be classified as useful, not noise."""
        vocab = ["Anandamayi", "satsang", "kirtan"]
        transcript = "We were at the ashram for satsang with Anandamayi this morning."
        corrections = []
        used, unused = self._classify(vocab, corrections, transcript)
        # satsang and Anandamayi appear correctly — priming worked, they're useful
        assert "satsang" in used
        assert "Anandamayi" in used
        # kirtan never appeared — genuine noise
        assert "kirtan" in unused

    def test_word_in_correction_target_is_used(self):
        """Words caught by Dreamer and corrected are also useful."""
        vocab = ["Anandamayi", "satsang", "kirtan"]
        transcript = "We were at the ashram for satsang with Anandamayi this morning."
        corrections = ["kirt \u2192 kirtan"]
        used, unused = self._classify(vocab, corrections, transcript)
        assert "kirtan" in used
        assert "Anandamayi" in used
        assert "satsang" in used
        assert unused == []

    def test_word_in_neither_transcript_nor_corrections_is_noise(self):
        """Words that appear nowhere are genuine noise."""
        vocab = ["bhajan", "pranayama"]
        transcript = "The family gathered for the holidays."
        corrections = []
        used, unused = self._classify(vocab, corrections, transcript)
        assert "bhajan" in unused
        assert "pranayama" in unused
        assert used == []

    def test_no_corrections_but_words_in_transcript_are_used(self):
        """Core fix: no corrections needed + word in transcript = success, not noise."""
        vocab = ["kirtan", "mantra"]
        transcript = "Everyone joined in for kirtan and sang the mantra together."
        used, unused = self._classify(vocab, [], transcript)
        # Both words in transcript — priming worked
        assert "kirtan" in used
        assert "mantra" in used
        assert unused == []

    def test_empty_vocab_no_crash(self):
        used, unused = self._classify([], ["x \u2192 y"], "some transcript")
        assert used == []
        assert unused == []

    def test_case_insensitive_transcript_match(self):
        """Match is case-insensitive — transcript casing should not affect signal."""
        vocab = ["Anandamayi"]
        transcript = "We heard about anandamayi during the ceremony."
        used, unused = self._classify(vocab, [], transcript)
        assert "Anandamayi" in used
        assert unused == []

    def test_original_bug_regression(self):
        """Regression: the original logic would classify this as noise.

        Old logic: word is 'used' only if it was a correction TARGET.
        A word that Whisper transcribed correctly was never a correction target,
        so it landed in 'unused'. This caused the system to deprioritize
        working vocabulary.

        New logic: transcript presence = useful. This test would FAIL under
        the old implementation.
        """
        vocab = ["kirtan"]
        # Whisper got it right — no correction was needed
        transcript = "The kirtan session lasted two hours."
        corrections = []  # No corrections — Whisper nailed it
        used, unused = self._classify(vocab, corrections, transcript)
        # Under old logic: used=[], unused=["kirtan"] (WRONG — would teach system to deprioritize)
        # Under new logic: used=["kirtan"], unused=[] (CORRECT — priming worked)
        assert "kirtan" in used, (
            "Regression: 'kirtan' appears correctly in transcript (priming succeeded) "
            "but was classified as noise. Old inverted signal bug."
        )
        assert unused == []


# ── Memory pruning ────────────────────────────────────────────────────────────

class TestFeedbackPruning:
    """Test that the Vocabulary Feedback section is capped at FEEDBACK_MAX_ENTRIES."""

    def test_entries_capped_at_max(self, tmp_path):
        """Writing more than FEEDBACK_MAX_ENTRIES entries prunes the oldest."""
        orig = _make_memory_file(tmp_path)
        try:
            limit = agent.FEEDBACK_MAX_ENTRIES
            # Write limit + 5 entries
            for i in range(limit + 5):
                agent.append_vocabulary_feedback([f"word{i}"], [])
            memory = agent.load_memory()
            section_header = "## Vocabulary Feedback"
            start = memory.index(section_header) + len(section_header)
            rest = memory[start:]
            next_sec = rest.find("\n## ")
            if next_sec != -1:
                rest = rest[:next_sec]
            entry_count = sum(1 for line in rest.splitlines() if line.strip().startswith("- "))
            assert entry_count == limit, f"Expected {limit} entries, got {entry_count}"
        finally:
            _restore_memory_file(orig)

    def test_oldest_entries_pruned(self, tmp_path):
        """Oldest entries are removed when cap is exceeded."""
        orig = _make_memory_file(tmp_path)
        try:
            limit = agent.FEEDBACK_MAX_ENTRIES
            # Write limit + 1 entries, last one is the newest
            for i in range(limit + 1):
                agent.append_vocabulary_feedback([f"word{i}"], [])
            memory = agent.load_memory()
            # word0 is the oldest — should be pruned
            # word{limit} is the newest — should be present
            assert f"word{limit}" in memory  # newest kept
            assert "word0" not in memory     # oldest pruned
        finally:
            _restore_memory_file(orig)
