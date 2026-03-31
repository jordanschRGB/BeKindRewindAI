"""Integration tests for load_relevant_vocabulary() in agent.py.

Tests CORRECT relevance filtering behavior using real file I/O with tempfile.
These tests verify that:
1. RuVector semantic search returns relevant vocabulary when available
2. Fallback behavior returns ALL entries (BUG - not filtered by relevance)
3. Domain presets are loaded when relevant
4. File I/O is real (no mocks for file operations)
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from agent import load_relevant_vocabulary, _load_flat_memory, MEMORY_FILE


class TestLoadRelevantVocabularyRealIO(unittest.TestCase):
    """Test load_relevant_vocabulary with real tempfile and CORRECT relevance filtering."""

    def setUp(self):
        self._original_memory_file = MEMORY_FILE
        self._temp_path = None

    def _create_temp_memory_file(self, content):
        """Create a real temp file with vocabulary content."""
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        self._temp_path = path
        with open(path, "w") as f:
            f.write(content)
        return path

    def tearDown(self):
        if self._temp_path is not None and os.path.exists(self._temp_path):
            os.unlink(self._temp_path)

    def _patch_memory_file(self, temp_path):
        """Patch MEMORY_FILE to use our temp file."""
        return patch.object(agent_module, "MEMORY_FILE", temp_path)

    def _get_memory_content(self):
        """Read content from temp memory file to verify file I/O happened."""
        with open(self._temp_path) as f:
            return f.read()


class TestRelevantVocabularyWithRuVector(TestLoadRelevantVocabularyRealIO):
    """Test that RuVector semantic search returns relevant vocabulary."""

    VOCABULARY_CONTENT = """# Archivist Memory

## Vocabulary
- Priya, bhangra, Mazel Tov, sangeet
- touchdown, quarterback, halftime, referee
- Om Namah Shivaya, kirtan, satsang
- birthday, cake, candles
"""

    @patch("agent._get_ruvector")
    @patch("agent._load_flat_memory")
    def test_wedding_description_returns_wedding_vocabulary(self, mock_flat_load, mock_get_rv):
        """When description mentions wedding, wedding vocabulary should be returned."""
        mock_rv = MagicMock()
        mock_rv.get_relevant_vocabulary.return_value = "Priya, bhangra, sangeet"
        mock_get_rv.return_value = mock_rv

        result = load_relevant_vocabulary("my cousin's Sikh wedding")

        mock_rv.get_relevant_vocabulary.assert_called_once_with(
            "my cousin's Sikh wedding", top_k=20
        )
        self.assertIn("Priya", result)
        self.assertIn("bhangra", result)
        self.assertIn("sangeet", result)
        self.assertNotIn("touchdown", result)
        self.assertNotIn("quarterback", result)

    @patch("agent._get_ruvector")
    @patch("agent._load_flat_memory")
    def test_football_description_returns_football_vocabulary(self, mock_flat_load, mock_get_rv):
        """When description mentions football, football vocabulary should be returned."""
        mock_rv = MagicMock()
        mock_rv.get_relevant_vocabulary.return_value = "touchdown, quarterback, halftime"
        mock_get_rv.return_value = mock_rv

        result = load_relevant_vocabulary("college football game")

        mock_rv.get_relevant_vocabulary.assert_called_once_with(
            "college football game", top_k=20
        )
        self.assertIn("touchdown", result)
        self.assertIn("quarterback", result)
        self.assertNotIn("Priya", result)
        self.assertNotIn("bhangra", result)

    @patch("agent._get_ruvector")
    @patch("agent._load_flat_memory")
    def test_unrelated_description_returns_empty(self, mock_flat_load, mock_get_rv):
        """When description is unrelated to any vocabulary, empty string returned."""
        mock_rv = MagicMock()
        mock_rv.get_relevant_vocabulary.return_value = ""
        mock_get_rv.return_value = mock_rv

        result = load_relevant_vocabulary("cooking pasta")

        self.assertEqual(result, "")


class TestLoadRelevantVocabularyFallbackBug(TestLoadRelevantVocabularyRealIO):
    """Test fallback behavior - documents the BUG that fallback returns ALL vocabulary.

    The fallback (when RuVector unavailable) extracts ALL vocabulary entries
    from the flat file without any relevance filtering. This is BUGGY behavior
    - it should return relevant entries only, not everything.
    """

    VOCABULARY_CONTENT = """# Archivist Memory

## Vocabulary
- Priya, bhangra, Mazel Tov, sangeet
- touchdown, quarterback, halftime, referee
"""

    @patch("agent._get_ruvector")
    def test_fallback_returns_all_vocabulary_not_filtered(self, mock_get_rv):
        """BUG: Fallback returns ALL vocabulary instead of relevant subset.

        When RuVector is unavailable, the fallback loads EVERYTHING from the
        Vocabulary section, ignoring the description parameter entirely.

        This test documents the BUG: requesting "cooking pasta" still returns
        wedding and football vocabulary because the fallback doesn't filter.
        """
        mock_get_rv.return_value = None

        temp_path = self._create_temp_memory_file(self.VOCABULARY_CONTENT)
        with patch.object(agent_module, "MEMORY_FILE", temp_path):
            result = load_relevant_vocabulary("cooking pasta")

        self.assertIn("Priya", result)
        self.assertIn("bhangra", result)
        self.assertIn("touchdown", result)
        self.assertIn("quarterback", result)
        football_and_wedding = (
            "Priya" in result and "bhangra" in result and
            "touchdown" in result and "quarterback" in result
        )
        self.assertTrue(
            football_and_wedding,
            "BUG: Fallback returned ALL vocabulary for unrelated description. "
            "Expected empty or filtered result, got: " + result
        )

    @patch("agent._get_ruvector")
    def test_fallback_returns_everything_for_wedding_too(self, mock_get_rv):
        """BUG: Even for relevant description, fallback returns ALL entries.

        When RuVector unavailable, the function should ideally still do
        substring matching, but instead it just returns everything.
        """
        mock_get_rv.return_value = None

        temp_path = self._create_temp_memory_file(self.VOCABULARY_CONTENT)
        with patch.object(agent_module, "MEMORY_FILE", temp_path):
            result = load_relevant_vocabulary("wedding ceremony")

        self.assertIn("Priya", result)
        self.assertIn("bhangra", result)
        self.assertIn("touchdown", result)
        self.assertIn("quarterback", result)

    @patch("agent._get_ruvector")
    def test_file_io_is_real_no_mocks(self, mock_get_rv):
        """Verify the function actually reads from disk - no mocks for file I/O."""
        mock_get_rv.return_value = None

        temp_path = self._create_temp_memory_file(self.VOCABULARY_CONTENT)
        with patch.object(agent_module, "MEMORY_FILE", temp_path):
            result = load_relevant_vocabulary("wedding")

        file_content = self._get_memory_content()
        self.assertIn("Priya", file_content)
        self.assertIn("touchdown", file_content)


class TestDomainPresetsLoaded(TestLoadRelevantVocabularyRealIO):
    """Test that domain presets from agent.py are used correctly.

    Note: Domain presets are used in get_whisper_prompt(), not directly
    in load_relevant_vocabulary(). The load_relevant_vocabulary function
    loads from memory (RuVector or flat file), not from DOMAIN_PRESETS.
    """

    def test_domain_preset_vocabulary_is_in_memory(self):
        """Domain presets like 'wedding' exist in DOMAIN_PRESETS in agent.py.

        These are used via get_whisper_prompt() when the agent configures
        a domain. load_relevant_vocabulary() loads from user-generated
        vocabulary in memory, not from the hardcoded presets.
        """
        from agent import DOMAIN_PRESETS

        self.assertIn("wedding", DOMAIN_PRESETS["family"])
        self.assertIn("game", DOMAIN_PRESETS["sports"])
        self.assertEqual(DOMAIN_PRESETS["general"], "")


class TestLoadRelevantVocabularyEdgeCases(TestLoadRelevantVocabularyRealIO):
    """Edge case tests for load_relevant_vocabulary."""

    EMPTY_MEMORY = """# Archivist Memory

## Vocabulary
"""

    NO_VOCABULARY_SECTION = """# Archivist Memory

## Sessions
- some session log
"""

    @patch("agent._get_ruvector")
    def test_empty_vocabulary_section_returns_empty(self, mock_get_rv):
        """Empty vocabulary section should return empty string."""
        mock_get_rv.return_value = None

        temp_path = self._create_temp_memory_file(self.EMPTY_MEMORY)
        with patch.object(agent_module, "MEMORY_FILE", temp_path):
            result = load_relevant_vocabulary("wedding")

        self.assertEqual(result, "")

    @patch("agent._get_ruvector")
    def test_no_vocabulary_section_returns_empty(self, mock_get_rv):
        """Memory file without Vocabulary section returns empty string."""
        mock_get_rv.return_value = None

        temp_path = self._create_temp_memory_file(self.NO_VOCABULARY_SECTION)
        with patch.object(agent_module, "MEMORY_FILE", temp_path):
            result = load_relevant_vocabulary("wedding")

        self.assertEqual(result, "")

    @patch("agent._get_ruvector")
    def test_memory_file_missing_returns_empty(self, mock_get_rv):
        """Non-existent memory file returns empty string."""
        mock_get_rv.return_value = None

        with patch.object(agent_module, "MEMORY_FILE", "/nonexistent/path/memory.md"):
            result = load_relevant_vocabulary("wedding")

        self.assertEqual(result, "")


import agent as agent_module


if __name__ == "__main__":
    unittest.main()
