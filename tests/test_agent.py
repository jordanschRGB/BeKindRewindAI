"""Tests for the vocabulary feedback loop in agent.py.

The feedback loop: scorer identifies mangled terms → append_vocabulary() stores corrections
→ load_relevant_vocabulary() retrieves them for next tape.

These tests mock RuVector entirely — they work with ONLY the flat markdown file.
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from agent import (
    append_vocabulary,
    load_relevant_vocabulary,
)


class TestVocabularyFeedbackLoop(unittest.TestCase):
    """Test the full vocabulary correction feedback loop."""

    def setUp(self):
        """Use a temp memory file so tests don't affect real data."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_memory_file = os.path.join(self.temp_dir, "test_memory.md")

    def tearDown(self):
        if os.path.exists(self.temp_memory_file):
            os.remove(self.temp_memory_file)
        os.rmdir(self.temp_dir)

    def _mock_flat_memory(self):
        """Patch agent module to use temp memory file."""
        def load_mem():
            if os.path.exists(self.temp_memory_file):
                with open(self.temp_memory_file) as f:
                    return f.read()
            return ""

        def save_mem(content):
            os.makedirs(os.path.dirname(self.temp_memory_file), exist_ok=True)
            with open(self.temp_memory_file, "w") as f:
                f.write(content)

        return patch.multiple(
            "agent",
            MEMORY_FILE=self.temp_memory_file,
            _load_flat_memory=load_mem,
            save_memory=save_mem,
        )

    def test_first_call_no_vocabulary(self):
        """load_relevant_vocabulary returns empty when no vocabulary stored yet."""
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            result = load_relevant_vocabulary("Sikh wedding with bhangra")
        self.assertEqual(result, "")

    def test_append_vocabulary_stores_corrections(self):
        """append_vocabulary writes corrections to flat file."""
        corrections = "Harjit, bhangra, Sikh wedding, Priya, Mazel Tov"
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary(corrections)
        self.assertTrue(os.path.exists(self.temp_memory_file))
        with open(self.temp_memory_file) as f:
            content = f.read()
        self.assertIn("## Vocabulary", content)
        self.assertIn(corrections, content)

    def test_load_relevant_vocabulary_returns_stored_corrections(self):
        """Second call with same domain returns stored vocabulary corrections."""
        corrections = "Harjit, bhangra, Sikh wedding, Priya"
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary(corrections)
            result = load_relevant_vocabulary("Sikh wedding with bhangra")
        self.assertIn("Harjit", result)
        self.assertIn("bhangra", result)
        self.assertIn("Sikh wedding", result)
        self.assertIn("Priya", result)

    def test_vocabulary_persists_across_separate_calls(self):
        """Vocabulary stored in first session is available in second session."""
        corrections = "Harjit, bhangra, Priya, Nan, Mazel Tov"
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary(corrections)

        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            result = load_relevant_vocabulary("cousin's Sikh wedding")

        self.assertIn("Harjit", result)
        self.assertIn("bhangra", result)
        self.assertIn("Priya", result)
        self.assertIn("Nan", result)
        self.assertIn("Mazel Tov", result)

    def test_multiple_append_vocabulary_accumulates(self):
        """Multiple calls to append_vocabulary accumulate entries."""
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary("Harjit, bhangra")
            append_vocabulary("Priya, Nan")
            result = load_relevant_vocabulary("wedding")

        self.assertIn("Harjit", result)
        self.assertIn("bhangra", result)
        self.assertIn("Priya", result)
        self.assertIn("Nan", result)

    def test_load_relevant_vocabulary_returns_all_vocabulary_fallback(self):
        """Without RuVector, load_relevant_vocabulary returns ALL stored vocabulary."""
        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary("Harjit, bhangra")
            result = load_relevant_vocabulary("football game")
        self.assertEqual(result, "Harjit, bhangra")

    def test_vocabulary_feedback_loop_full_simulation(self):
        """Simulate full feedback loop: scorer identifies mangled terms."""
        tape1_description = "My uncle's wedding in 1994. He married a woman named Priya. There's lots of dancing, we did a bhangra, and my auntie kept yelling 'Mazel Tov' even though it's a Sikh wedding. My nan's there too."

        corrections = "Harjit, Priya, Nan, bhangra, Mazel Tov (at Sikh wedding, not Hebrew), 1994"

        with self._mock_flat_memory(), patch("agent._get_ruvector", return_value=None):
            append_vocabulary(corrections)
            result = load_relevant_vocabulary(tape1_description)

        self.assertIn("Harjit", result)
        self.assertIn("Priya", result)
        self.assertIn("Nan", result)
        self.assertIn("bhangra", result)
        self.assertIn("Mazel Tov", result)
        self.assertIn("1994", result)

        self.assertNotIn("football", result)
        self.assertNotIn("basketball", result)


if __name__ == "__main__":
    unittest.main()
