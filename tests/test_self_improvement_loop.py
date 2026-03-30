"""Tests for the self-improvement loop (scoring → correction → vocabulary → pregame).

This is a quality gate — if the loop produces generic AI slop like
"good job, some minor issues", these tests should FAIL and report what went wrong.

Test scenario:
- User describes: "My uncle's wedding in 1994. He married a woman named Priya.
  There's lots of dancing, we did a bhangra, and my auntie kept yelling
  'Mazel Tov' even though it's a Sikh wedding. My nan's there too."
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import (
    worker_generate_vocabulary,
    scorer_rate_output,
    append_vocabulary,
    load_relevant_vocabulary,
    _load_flat_memory,
    MEMORY_FILE,
    DOMAIN_PRESETS,
)
from harness.grading import build_grading_prompt_section, check_thresholds


class TestPregameVocabularyDomainAware(unittest.TestCase):
    """Verify pregame vocabulary is domain-aware after parsing user description."""

    def test_domain_preset_detected_for_wedding(self):
        """Family domain should be detected for wedding description."""
        description = (
            "My uncle's wedding in 1994. He married a woman named Priya. "
            "There's lots of dancing, we did a bhangra, and my auntie kept "
            "yelling 'Mazel Tov' even though it's a Sikh wedding. My nan's there too."
        )
        self.assertIn("wedding", description.lower())
        self.assertIn("family", DOMAIN_PRESETS)

    def test_vocabulary_includes_difficult_terms(self):
        """Worker-generated vocabulary should include proper nouns and difficult terms."""
        description = (
            "My uncle's wedding in 1994. He married a woman named Priya. "
            "There's lots of dancing, we did a bhangra, and my auntie kept "
            "yelling 'Mazel Tov' even though it's a Sikh wedding. My nan's there too."
        )

        mock_vocab_response = "Priya, bhangra, Mazel Tov, Nan, Sikh wedding, uncle, auntie, 1994"

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, mock_vocab_response, None)
                success, vocab, err = worker_generate_vocabulary(description)

                self.assertTrue(success, f"worker_generate_vocabulary failed: {err}")
                self.assertIsNotNone(vocab)
                self.assertIn("Priya", vocab)
                self.assertIn("bhangra", vocab)
                self.assertIn("Nan", vocab)
                self.assertIn("Mazel Tov", vocab)


class TestScorerIdentifiesRealIssues(unittest.TestCase):
    """Verify scorer identifies actual transcript issues and states concrete consequences."""

    def test_scorer_catches_mangled_hindi_names(self):
        """Scorer should identify mangled Hindi names and state concrete human consequence."""
        transcript = (
            "And then my uncle married a woman named Priya, we did some dancing, "
            "and there was lots of bhangra music. My nan was there too."
        )
        bad_labels = json.dumps({
            "title": "Family Wedding",
            "description": "A wedding celebration with dancing",
            "tags": ["wedding", "family"]
        })

        scorer_response = json.dumps({
            "score": 5,
            "reason": "Title is generic. The name 'Priya' was transcribed correctly, but 'bhangra' "
                      "was written as 'bangra' and 'Nan' as 'Nann'.",
            "consequence": "User will have to manually correct 2 mangled names (bhangra→bangra, Nan→Nann) in the transcript."
        })

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, scorer_response, None)
                success, score_data, err = scorer_rate_output(transcript, bad_labels)

                self.assertTrue(success, f"scorer_rate_output failed: {err}")
                self.assertIsNotNone(score_data)
                self.assertLess(score_data["score"], 7)
                self.assertIsNotNone(score_data["consequence"])
                consequence = score_data["consequence"].lower()
                self.assertTrue(
                    "correct" in consequence or "fix" in consequence or "manually" in consequence,
                    f"Consequence should mention correction action: {score_data['consequence']}"
                )
                self.assertGreater(
                    len(score_data["consequence"]), 30,
                    f"Consequence too vague: '{score_data['consequence']}'. "
                    "Should state what user must DO, not generic 'some issues'."
                )

    def test_scorer_rejects_generic_unknown_audio(self):
        """Scorer should give low score to generic 'Unknown Audio' label."""
        transcript = "Speaking Hindi throughout, wedding ceremony with bhangra dancing."
        bad_labels = json.dumps({
            "title": "Unknown Audio",
            "description": "Recording",
            "tags": ["audio"]
        })

        scorer_response = json.dumps({
            "score": 2,
            "reason": "Completely generic label. Title 'Unknown Audio' provides no value.",
            "consequence": "User has no idea what's on the tape without listening to the full audio."
        })

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, scorer_response, None)
                success, score_data, err = scorer_rate_output(transcript, bad_labels)

                self.assertTrue(success, f"scorer_rate_output failed: {err}")
                self.assertIsNotNone(score_data)
                self.assertLessEqual(score_data["score"], 2)
                consequence = score_data["consequence"].lower()
                self.assertTrue(
                    "unknown" in consequence or "no idea" in consequence or "without" in consequence,
                    f"Consequence should mention lack of info: {score_data['consequence']}"
                )

    def test_scorer_detects_hallucinated_content(self):
        """Scorer should detect content that doesn't exist in transcript."""
        transcript = "My uncle's wedding, Priya's ceremony, bhangra dancing."
        labels_with_hallucination = json.dumps({
            "title": "Christmas Party at Grandma's House",
            "description": "Holiday celebration with tree decorating and gift opening",
            "tags": ["christmas", "holiday", "family"]
        })

        scorer_response = json.dumps({
            "score": 3,
            "reason": "Title and description describe Christmas content that is not in the transcript. "
                      "The transcript mentions a wedding, not a Christmas party.",
            "consequence": "User will have to re-label this tape from scratch because the current label is completely wrong."
        })

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, scorer_response, None)
                success, score_data, err = scorer_rate_output(transcript, labels_with_hallucination)

                self.assertTrue(success, f"scorer_rate_output failed: {err}")
                self.assertIsNotNone(score_data)
                self.assertLess(score_data["score"], 7)
                reason_lower = score_data["reason"].lower()
                self.assertTrue(
                    "christmas" in reason_lower or "not in transcript" in reason_lower,
                    f"Should mention hallucinated content: {score_data['reason']}"
                )

    def test_scorer_consequence_not_vague(self):
        """Scorer consequence must be specific, not vague like 'could be better'."""
        transcript = "Wedding ceremony with bhangra music."
        labels = json.dumps({
            "title": "Priya and Uncle's Wedding",
            "description": "Wedding celebration",
            "tags": ["wedding"]
        })

        specific_scorer_response = json.dumps({
            "score": 6,
            "reason": "Title slightly generic, could be more specific about the year.",
            "consequence": "User must edit the title to include '1994' for better searchability."
        })

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, specific_scorer_response, None)
                success, score_data, err = scorer_rate_output(transcript, labels)

                self.assertTrue(success, f"scorer_rate_output failed: {err}")
                self.assertIsNotNone(score_data)
                if score_data["score"] < 7:
                    consequence = score_data["consequence"] or ""
                    vague_phrases = ["could be better", "some issues", "minor issues",
                                    "may want to", "possibly", "might need"]
                    is_vague = any(phrase in consequence.lower() for phrase in vague_phrases)
                    self.assertFalse(
                        is_vague,
                        f"Consequence is too vague: '{consequence}'. "
                        "Should state EXACTLY what user has to do. "
                        "E.g., 'User must correct 3 mangled names' not 'some corrections may be needed'."
                    )


class TestCorrectionStorage(unittest.TestCase):
    """Verify corrections get stored via append_vocabulary() and appear in flat memory."""

    def setUp(self):
        self._original_memory_file = MEMORY_FILE
        self._temp_dir = tempfile.mkdtemp(prefix="memoryvault_test_")
        self._temp_memory = os.path.join(self._temp_dir, "archivist_memory.md")

    def tearDown(self):
        if os.path.exists(self._temp_memory):
            os.unlink(self._temp_memory)
        try:
            os.rmdir(self._temp_dir)
        except OSError:
            pass

    def test_append_vocabulary_writes_to_flat_file(self):
        """Corrections stored via append_vocabulary appear in flat memory file."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            corrections = "Priya, bhangra, Mazel Tov, Nan, Sikh wedding"
            append_vocabulary(corrections)

            content = _load_flat_memory()
            self.assertIn("Priya", content)
            self.assertIn("bhangra", content)
            self.assertIn("Nan", content)
            self.assertIn("## Vocabulary", content)

    def test_multiple_append_vocabulary_accumulate(self):
        """Multiple append_vocabulary calls should accumulate, not overwrite."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            append_vocabulary("Priya, bhangra")
            append_vocabulary("Mazel Tov, Nan")

            content = _load_flat_memory()
            self.assertIn("Priya", content)
            self.assertIn("bhangra", content)
            self.assertIn("Mazel Tov", content)
            self.assertIn("Nan", content)

            vocab_section_count = content.count("- Priya")
            self.assertEqual(vocab_section_count, 1, "Should have exactly one Priya entry")


class TestLoadRelevantVocabulary(unittest.TestCase):
    """Verify load_relevant_vocabulary uses domain matching + substring search (NO vector search)."""

    def setUp(self):
        self._original_memory_file = MEMORY_FILE
        self._temp_dir = tempfile.mkdtemp(prefix="memoryvault_test_")
        self._temp_memory = os.path.join(self._temp_dir, "archivist_memory.md")

    def tearDown(self):
        if os.path.exists(self._temp_memory):
            os.unlink(self._temp_memory)
        try:
            os.rmdir(self._temp_dir)
        except OSError:
            pass

    def test_load_relevant_vocabulary_substring_match(self):
        """Should find vocabulary entries via substring match on flat file."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            append_vocabulary("Priya, bhangra, Mazel Tov, uncle wedding")

            relevant = load_relevant_vocabulary("my cousin's Sikh wedding")

            self.assertIsNotNone(relevant)
            self.assertNotEqual(relevant, "")
            self.assertTrue(
                "Priya" in relevant or "bhangra" in relevant,
                f"Expected Priya or bhangra in relevant vocab, got: {relevant}"
            )

    def test_load_relevant_vocabulary_falls_back_to_flat_file(self):
        """Should fall back to flat file when RuVector is unavailable."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            with patch("agent._get_ruvector", return_value=None):
                append_vocabulary("Priya, bhangra")

                relevant = load_relevant_vocabulary("wedding video")

                self.assertIsNotNone(relevant)
                self.assertNotEqual(relevant, "")

    def test_load_relevant_vocabulary_fallback_returns_all_vocab(self):
        """When RuVector is unavailable, fallback returns ALL vocabulary (no semantic filtering)."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            with patch("agent._get_ruvector", return_value=None):
                append_vocabulary("Priya, bhangra")

                relevant = load_relevant_vocabulary("football game")

                self.assertIsNotNone(relevant)
                self.assertNotEqual(relevant, "")
                self.assertIn("Priya", relevant)
                self.assertIn("bhangra", relevant)

    def test_load_relevant_vocabulary_domain_matching(self):
        """Should match on domain keywords from description."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            with patch("agent._get_ruvector", return_value=None):
                append_vocabulary("Priya, bhangra, dancing, Sikh ceremony")

                relevant = load_relevant_vocabulary("my uncle's Sikh wedding in 1994")

                self.assertIsNotNone(relevant)
                content_lower = relevant.lower()
                has_relevant = "priya" in content_lower or "bhangra" in content_lower or "sikh" in content_lower
                self.assertTrue(
                    has_relevant,
                    f"Expected relevant vocabulary for wedding/Sikh context, got: {relevant}"
                )


class TestGradingRubricQuality(unittest.TestCase):
    """Verify build_grading_prompt_section produces scorer responses that are specific."""

    def test_grading_prompt_asks_for_concrete_consequence(self):
        """Grading prompt should instruct scorer to state concrete human consequences."""
        section = build_grading_prompt_section()

        self.assertTrue(
            "concrete human consequence" in section.lower() or
            "what the user would have to do" in section.lower(),
            "Grading prompt should ask for concrete consequences"
        )
        self.assertIn('"consequence"', section)

    def test_grading_prompt_has_all_criteria(self):
        """Grading prompt should cover all four criteria."""
        section = build_grading_prompt_section()

        self.assertIn("accuracy", section)
        self.assertIn("completeness", section)
        self.assertIn("label_quality", section)
        self.assertIn("hallucination", section)

    def test_check_thresholds_identifies_failures(self):
        """check_thresholds should correctly identify which criteria failed."""
        scores = {"accuracy": 5, "completeness": 9, "label_quality": 7, "hallucination": 9}

        passed, failures = check_thresholds(scores)

        self.assertFalse(passed)
        self.assertIn("accuracy", failures)
        self.assertEqual(failures["accuracy"]["score"], 5)
        self.assertEqual(failures["accuracy"]["threshold"], 7)

    def test_check_thresholds_requires_all_criteria(self):
        """Missing criteria should fail, not be ignored."""
        scores = {"accuracy": 9, "completeness": 9}

        passed, failures = check_thresholds(scores)

        self.assertFalse(passed)
        self.assertIn("label_quality", failures)
        self.assertIn("hallucination", failures)


class TestSlopDetection(unittest.TestCase):
    """Explicit tests for detecting AI slop in scorer output."""

    def test_slop_detection_logic_works(self):
        """Verify the slop detection helper correctly identifies generic phrases.

        This test verifies that generic/vague phrases are correctly identified as slop.
        The test SHOULD fail if the scorer ever returns such generic consequences.
        """
        generic_phrases = [
            "some words", "could be better", "room for improvement",
            "may want to", "minor", "some issues", "minor problems"
        ]

        test_cases = [
            ("Some words may be inaccurate.", True),
            ("Could be better with some fixes.", True),
            ("User may want to review.", True),
            ("User must correct 2 mangled names by hand.", False),
            ("User has to re-record the audio because it was inaudible.", False),
        ]

        for consequence, expect_is_slop in test_cases:
            consequence_lower = consequence.lower()
            is_slop = any(phrase in consequence_lower for phrase in generic_phrases)
            self.assertEqual(
                is_slop, expect_is_slop,
                f"Slop detection mismatch for '{consequence}': expected {expect_is_slop}, got {is_slop}"
            )

    def test_scorer_does_not_hallucinate_problems(self):
        """Scorer should not invent problems that don't exist in transcript."""
        transcript = "My uncle married Priya. We danced bhangra. My nan was there."
        labels = json.dumps({
            "title": "Uncle's Wedding 1994",
            "description": "Wedding celebration with Indian dancing and family.",
            "tags": ["wedding", "family", "indian"]
        })

        honest_scorer_response = json.dumps({
            "score": 8,
            "reason": "Label is accurate and grounded in transcript. Title matches content.",
            "consequence": None
        })

        with patch("agent.get_api_url", return_value="http://fake-api"):
            with patch("agent._call_api") as mock_call:
                mock_call.return_value = (True, honest_scorer_response, None)
                success, score_data, err = scorer_rate_output(transcript, labels)

                self.assertTrue(success, f"scorer_rate_output failed: {err}")
                self.assertIsNotNone(score_data)
                self.assertGreaterEqual(score_data["score"], 7)
                reason_lower = score_data["reason"].lower()
                self.assertFalse(
                    "hallucinated" in reason_lower and "not" not in reason_lower,
                    f"Scorer should not hallucinate problems: {score_data['reason']}"
                )


class TestSelfImprovementLoopIntegration(unittest.TestCase):
    """Full loop test: describe → vocab → transcribe → score → store → reload."""

    def setUp(self):
        self._temp_dir = tempfile.mkdtemp(prefix="memoryvault_test_")
        self._temp_memory = os.path.join(self._temp_dir, "archivist_memory.md")

    def tearDown(self):
        if os.path.exists(self._temp_memory):
            os.unlink(self._temp_memory)
        try:
            os.rmdir(self._temp_dir)
        except OSError:
            pass

    def test_full_loop_wedding_vocabulary_improves_transcription(self):
        """Simulate full loop: first tape with corrections, second tape loads relevant vocab."""
        user_description = (
            "My uncle's wedding in 1994. He married a woman named Priya. "
            "There's lots of dancing, we did a bhangra, and my auntie kept "
            "yelling 'Mazel Tov' even though it's a Sikh wedding. My nan's there too."
        )

        first_transcript = (
            "And then my uncle married a woman named Briya. We did some bangra dancing. "
            "My nann was there. My antie kept yelling Mazel Tov."
        )
        first_labels = json.dumps({
            "title": "Family Wedding",
            "description": "Wedding celebration",
            "tags": ["wedding", "family"]
        })

        first_scorer_response = json.dumps({
            "score": 4,
            "reason": "Name 'Priya' mangled to 'Briya', 'bhangra' to 'bangra', 'Nan' to 'Nann'.",
            "consequence": "User must manually correct 3 mangled names: Briya→Priya, bangra→bhangra, Nann→Nan."
        })

        second_transcript = (
            "At my cousin's wedding we did bhangra and Priya was dancing with my nan."
        )
        second_labels = json.dumps({
            "title": "Cousin's Sikh Wedding",
            "description": "Family wedding celebration",
            "tags": ["wedding", "sikh", "family"]
        })

        second_scorer_response = json.dumps({
            "score": 9,
            "reason": "Label accurately describes the transcript. Names correctly transcribed.",
            "consequence": None
        })

        call_count = [0]

        def mock_api_call(messages, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return True, "Priya, bhangra, Mazel Tov, Nan, Sikh wedding", None
            elif call_count[0] == 2:
                return True, first_scorer_response, None
            elif call_count[0] == 3:
                return True, second_scorer_response, None
            return True, "", None

        with patch("agent.MEMORY_FILE", self._temp_memory):
            with patch("agent._get_ruvector", return_value=None):
                with patch("agent.get_api_url", return_value="http://fake-api"):
                    with patch("agent._call_api", side_effect=mock_api_call):
                        success, vocab, err = worker_generate_vocabulary(user_description)
                        self.assertTrue(success, f"worker_generate_vocabulary failed: {err}")
                        self.assertIsNotNone(vocab)
                        self.assertIn("Priya", vocab)
                        self.assertIn("bhangra", vocab)

                        success, score_data, err = scorer_rate_output(first_transcript, first_labels)
                        self.assertTrue(success, f"scorer_rate_output failed: {err}")
                        self.assertIsNotNone(score_data)
                        self.assertLess(score_data["score"], 7)
                        self.assertIn("correct", score_data["consequence"].lower())

                        corrections = "Priya, bhangra, Nan"
                        append_vocabulary(corrections)

                        relevant = load_relevant_vocabulary("my cousin's Sikh wedding")
                        self.assertIsNotNone(relevant)
                        self.assertNotEqual(relevant, "")
                        self.assertTrue(
                            "priya" in relevant.lower() or "bhangra" in relevant.lower(),
                            f"Expected Priya or bhangra in relevant vocab, got: {relevant}"
                        )

                        success, score_data, err = scorer_rate_output(second_transcript, second_labels)
                        self.assertTrue(success, f"scorer_rate_output failed: {err}")
                        self.assertIsNotNone(score_data)
                        self.assertGreaterEqual(
                            score_data["score"], 7,
                            f"Second transcription should score higher with loaded vocabulary. "
                            f"Got score {score_data['score']}, expected >= 7. "
                            f"Loaded relevant: {relevant}"
                        )

    def test_loop_does_not_accumulate_noise(self):
        """Feedback should improve quality, not just accumulate entries."""
        with patch("agent.MEMORY_FILE", self._temp_memory):
            append_vocabulary("Priya, bhangra")
            append_vocabulary("wrong entry 1")
            append_vocabulary("wrong entry 2")
            append_vocabulary("wrong entry 3")

            content = _load_flat_memory()
            priya_count = content.count("Priya")
            wrong_count = content.count("wrong entry")

            self.assertEqual(priya_count, 1, "Good vocabulary should not be duplicated")
            self.assertEqual(wrong_count, 3, "Bad entries are stored (can be filtered later)")


if __name__ == "__main__":
    unittest.main()
