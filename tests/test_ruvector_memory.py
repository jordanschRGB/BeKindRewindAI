"""Tests for the RuVector memory backend (harness/memory.py).

All subprocess calls are mocked -- no actual mcporter or RuVector needed.
"""

import json
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from harness.memory import (
    _mcporter_call,
    is_available,
    search_memory,
    store_memory,
    store_vocabulary,
    store_session,
    get_relevant_vocabulary,
    DB_PATH,
)


class TestMcporterCall(unittest.TestCase):
    """Test the low-level mcporter wrapper."""

    @patch("harness.memory.subprocess.run")
    def test_successful_json_response(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"results": []}',
            stderr="",
        )
        ok, data = _mcporter_call("ruvector.vector_db_stats", db_path="/tmp/test.db")
        self.assertTrue(ok)
        self.assertEqual(data, {"results": []})
        mock_run.assert_called_once()

    @patch("harness.memory.subprocess.run")
    def test_nonzero_return_code(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="connection refused",
        )
        ok, data = _mcporter_call("ruvector.vector_db_stats", db_path="/tmp/test.db")
        self.assertFalse(ok)
        self.assertIsNone(data)

    @patch("harness.memory.subprocess.run")
    def test_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="mcporter", timeout=10)
        ok, data = _mcporter_call("ruvector.vector_db_stats", db_path="/tmp/test.db")
        self.assertFalse(ok)
        self.assertIsNone(data)

    @patch("harness.memory.subprocess.run")
    def test_mcporter_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        ok, data = _mcporter_call("ruvector.vector_db_stats", db_path="/tmp/test.db")
        self.assertFalse(ok)
        self.assertIsNone(data)

    @patch("harness.memory.subprocess.run")
    def test_empty_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        ok, data = _mcporter_call("ruvector.vector_db_insert", db_path="/tmp/test.db", content="test")
        self.assertTrue(ok)
        self.assertIsNone(data)

    @patch("harness.memory.subprocess.run")
    def test_plain_text_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="OK inserted", stderr="")
        ok, data = _mcporter_call("ruvector.vector_db_insert", db_path="/tmp/test.db", content="test")
        self.assertTrue(ok)
        self.assertEqual(data, "OK inserted")

    @patch("harness.memory.subprocess.run")
    def test_dict_metadata_serialized(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        metadata = {"type": "vocabulary", "session": "2026-03-25"}
        _mcporter_call("ruvector.vector_db_insert", db_path="/tmp/test.db", metadata=metadata)
        cmd = mock_run.call_args[0][0]
        # metadata should be JSON-serialized in the command
        self.assertIn(f'metadata={json.dumps(metadata)}', " ".join(cmd))


class TestIsAvailable(unittest.TestCase):

    @patch("harness.memory._mcporter_call")
    def test_available(self, mock_call):
        mock_call.return_value = (True, {"count": 42})
        self.assertTrue(is_available())
        mock_call.assert_called_once_with("ruvector.vector_db_stats", db_path=DB_PATH)

    @patch("harness.memory._mcporter_call")
    def test_unavailable(self, mock_call):
        mock_call.return_value = (False, None)
        self.assertFalse(is_available())


class TestSearchMemory(unittest.TestCase):

    @patch("harness.memory._mcporter_call")
    def test_returns_list(self, mock_call):
        results = [{"content": "vocab1", "score": 0.9}, {"content": "vocab2", "score": 0.8}]
        mock_call.return_value = (True, results)
        self.assertEqual(search_memory("test query"), results)

    @patch("harness.memory._mcporter_call")
    def test_returns_wrapped_results(self, mock_call):
        results = [{"content": "vocab1"}]
        mock_call.return_value = (True, {"results": results})
        self.assertEqual(search_memory("test query"), results)

    @patch("harness.memory._mcporter_call")
    def test_failure_returns_empty(self, mock_call):
        mock_call.return_value = (False, None)
        self.assertEqual(search_memory("test query"), [])

    @patch("harness.memory._mcporter_call")
    def test_custom_top_k(self, mock_call):
        mock_call.return_value = (True, [])
        search_memory("query", top_k=5)
        mock_call.assert_called_once_with(
            "ruvector.vector_db_search", db_path=DB_PATH, query="query", top_k=5
        )


class TestStoreMemory(unittest.TestCase):

    @patch("harness.memory._mcporter_call")
    def test_store_without_metadata(self, mock_call):
        mock_call.return_value = (True, None)
        self.assertTrue(store_memory("test content"))
        mock_call.assert_called_once_with(
            "ruvector.vector_db_insert", db_path=DB_PATH, content="test content"
        )

    @patch("harness.memory._mcporter_call")
    def test_store_with_metadata(self, mock_call):
        mock_call.return_value = (True, None)
        meta = {"type": "vocabulary"}
        self.assertTrue(store_memory("test content", meta))
        mock_call.assert_called_once_with(
            "ruvector.vector_db_insert", db_path=DB_PATH, content="test content", metadata=meta
        )

    @patch("harness.memory._mcporter_call")
    def test_store_failure(self, mock_call):
        mock_call.return_value = (False, None)
        self.assertFalse(store_memory("test content"))


class TestStoreVocabulary(unittest.TestCase):

    @patch("harness.memory.store_memory")
    def test_stores_with_vocabulary_metadata(self, mock_store):
        mock_store.return_value = True
        store_vocabulary("Om Namah Shivaya, satsang", session_id="2026-03-25")
        mock_store.assert_called_once()
        args = mock_store.call_args
        self.assertIn("Vocabulary:", args[0][0])
        meta = args[0][1]
        self.assertEqual(meta["type"], "vocabulary")
        self.assertEqual(meta["session"], "2026-03-25")

    @patch("harness.memory.time")
    @patch("harness.memory.store_memory")
    def test_default_session_id(self, mock_store, mock_time):
        mock_store.return_value = True
        mock_time.strftime.return_value = "2026-03-25_2357"
        store_vocabulary("test words")
        meta = mock_store.call_args[0][1]
        self.assertEqual(meta["session"], "2026-03-25_2357")


class TestStoreSession(unittest.TestCase):

    @patch("harness.memory.time")
    @patch("harness.memory.store_memory")
    def test_stores_session_log(self, mock_store, mock_time):
        mock_store.return_value = True
        mock_time.strftime.return_value = "2026-03-25 23:57"
        store_session("Captured tape 3 successfully")
        args = mock_store.call_args
        self.assertIn("Session:", args[0][0])
        self.assertIn("2026-03-25 23:57", args[0][0])
        self.assertEqual(args[0][1]["type"], "session_log")


class TestGetRelevantVocabulary(unittest.TestCase):

    @patch("harness.memory.search_memory")
    def test_extracts_vocabulary(self, mock_search):
        mock_search.return_value = [
            {"content": "Vocabulary: Om Namah Shivaya, satsang"},
            {"content": "Vocabulary: pranayama, asana"},
        ]
        result = get_relevant_vocabulary("yoga tape")
        self.assertIn("Om Namah Shivaya", result)
        self.assertIn("pranayama", result)

    @patch("harness.memory.search_memory")
    def test_handles_raw_content(self, mock_search):
        mock_search.return_value = [
            {"content": "some raw memory without prefix"},
        ]
        result = get_relevant_vocabulary("test")
        self.assertEqual(result, "some raw memory without prefix")

    @patch("harness.memory.search_memory")
    def test_empty_results(self, mock_search):
        mock_search.return_value = []
        result = get_relevant_vocabulary("test")
        self.assertEqual(result, "")

    @patch("harness.memory.search_memory")
    def test_custom_top_k(self, mock_search):
        mock_search.return_value = []
        get_relevant_vocabulary("test", top_k=5)
        mock_search.assert_called_once_with("vocabulary test", top_k=5)


if __name__ == "__main__":
    unittest.main()
