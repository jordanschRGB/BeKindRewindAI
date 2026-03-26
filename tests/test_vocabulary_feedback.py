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
    """Test the word-classification logic used in run_pipeline."""

    def _classify(self, vocab_words, corrections):
        """Replicate the classification logic from runner.py."""
        corrected_targets = set()
        for c in corrections:
            if " \u2192 " in c:
                corrected_targets.add(c.split(" \u2192 ")[1].strip())

        used = [w for w in vocab_words if w in corrected_targets]
        unused = [w for w in vocab_words if w not in corrected_targets]
        return used, unused

    def test_word_in_corrections_is_used(self):
        vocab = ["Anandamayi", "satsang", "kirtan"]
        corrections = ["ananda my \u2192 Anandamayi"]
        used, unused = self._classify(vocab, corrections)
        assert "Anandamayi" in used
        assert "satsang" in unused
        assert "kirtan" in unused

    def test_no_corrections_all_unused(self):
        vocab = ["kirtan", "mantra"]
        used, unused = self._classify(vocab, [])
        assert used == []
        assert set(unused) == {"kirtan", "mantra"}

    def test_all_corrections_all_used(self):
        vocab = ["kirtan", "satsang"]
        corrections = ["kirt \u2192 kirtan", "sat song \u2192 satsang"]
        used, unused = self._classify(vocab, corrections)
        assert set(used) == {"kirtan", "satsang"}
        assert unused == []

    def test_empty_vocab_no_crash(self):
        used, unused = self._classify([], ["x \u2192 y"])
        assert used == []
        assert unused == []

    def test_correction_target_not_in_vocab_ignored(self):
        # A correction whose target isn't a vocab word should not inflate used list
        vocab = ["kirtan"]
        corrections = ["x \u2192 something_else"]
        used, unused = self._classify(vocab, corrections)
        assert "kirtan" in unused
        assert used == []
