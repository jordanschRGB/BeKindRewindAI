"""RuVector memory backend for BeKindRewindAI.

Wraps mcporter CLI calls to RuVector's vector database.
All operations are non-blocking with graceful fallback on failure.
"""

import json
import logging
import subprocess
import time

logger = logging.getLogger(__name__)

DB_PATH = "/opt/ruvector/data/memoryvault.db"
MCPORTER_TIMEOUT = 10  # seconds


def _mcporter_call(tool, **kwargs):
    """Call an mcporter tool and return parsed output.

    Returns (success: bool, data: dict|list|str|None).
    """
    cmd = ["mcporter", "call", tool]
    for key, value in kwargs.items():
        if isinstance(value, (dict, list)):
            cmd.append(f"{key}={json.dumps(value)}")
        else:
            cmd.append(f"{key}={value}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=MCPORTER_TIMEOUT,
        )
        if result.returncode != 0:
            logger.warning("mcporter %s failed (rc=%d): %s", tool, result.returncode, result.stderr.strip())
            return False, None

        output = result.stdout.strip()
        if not output:
            return True, None

        try:
            return True, json.loads(output)
        except json.JSONDecodeError:
            return True, output

    except subprocess.TimeoutExpired:
        logger.warning("mcporter %s timed out after %ds", tool, MCPORTER_TIMEOUT)
        return False, None
    except FileNotFoundError:
        logger.warning("mcporter not found on PATH")
        return False, None
    except Exception as e:
        logger.warning("mcporter %s error: %s", tool, e)
        return False, None


def is_available():
    """Check if RuVector is reachable via mcporter."""
    ok, _ = _mcporter_call("ruvector.vector_db_stats", db_path=DB_PATH)
    return ok


def search_memory(query, top_k=10):
    """Semantic search across all stored memories.

    Returns list of results or empty list on failure.
    """
    ok, data = _mcporter_call(
        "ruvector.vector_db_search",
        db_path=DB_PATH,
        query=query,
        top_k=top_k,
    )
    if ok and isinstance(data, list):
        return data
    if ok and isinstance(data, dict) and "results" in data:
        return data["results"]
    return []


def store_memory(content, metadata=None):
    """Insert a memory into the vector database.

    Args:
        content: Text content to store and embed.
        metadata: Optional dict of typed metadata.

    Returns True on success, False on failure.
    """
    kwargs = {"db_path": DB_PATH, "content": content}
    if metadata:
        kwargs["metadata"] = metadata
    ok, _ = _mcporter_call("ruvector.vector_db_insert", **kwargs)
    return ok


def store_vocabulary(words, session_id=None):
    """Store vocabulary words with vocabulary-typed metadata.

    Args:
        words: Vocabulary string (comma-separated or free text).
        session_id: Optional session identifier (defaults to timestamp).
    """
    if not session_id:
        session_id = time.strftime("%Y-%m-%d_%H%M")

    metadata = {
        "type": "vocabulary",
        "session": session_id,
    }

    # Store as a single document with the full vocabulary list
    return store_memory(f"Vocabulary: {words}", metadata)


def store_session(summary):
    """Store a session log entry.

    Args:
        summary: Session summary text.
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M")
    metadata = {
        "type": "session_log",
        "timestamp": timestamp,
    }
    return store_memory(f"Session: {timestamp}: {summary}", metadata)


def get_relevant_vocabulary(description, top_k=20):
    """Retrieve vocabulary most relevant to a tape description.

    Instead of loading ALL vocabulary ever recorded, this does semantic
    search to find the top-k most relevant vocabulary entries for the
    current task. Biomimetic decay means frequently-accessed terms
    reinforce while one-off words fade naturally.

    Args:
        description: Description of what's being digitized.
        top_k: Maximum number of vocabulary entries to return.

    Returns a string of relevant vocabulary or empty string.
    """
    results = search_memory(f"vocabulary {description}", top_k=top_k)
    if not results:
        return ""

    # Extract content from results, filter to vocabulary entries
    vocab_parts = []
    for r in results:
        content = r.get("content", "") if isinstance(r, dict) else str(r)
        # Strip "Vocabulary: " prefix if present
        if content.startswith("Vocabulary: "):
            content = content[len("Vocabulary: "):]
        vocab_parts.append(content)

    return ", ".join(vocab_parts)
