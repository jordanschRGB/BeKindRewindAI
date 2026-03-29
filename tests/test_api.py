"""Tests for JSON API endpoints."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app


@pytest.fixture(autouse=True)
def reset_session():
    """Reset the module-level _session global between tests."""
    import api
    api._session = None
    yield
    api._session = None


def _make_client(tmp_path):
    app = create_app()
    app.config["OUTPUT_DIR"] = str(tmp_path / "output")
    app.config["CONFIG_DIR"] = str(tmp_path / "config")
    app.config["TESTING"] = True
    os.makedirs(app.config["OUTPUT_DIR"], exist_ok=True)
    os.makedirs(app.config["CONFIG_DIR"], exist_ok=True)
    return app.test_client()


def test_status(tmp_path):
    client = _make_client(tmp_path)
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "version" in data


def test_session_start(tmp_path):
    client = _make_client(tmp_path)
    r = client.post("/api/session/start", json={"tape_count": 3})
    assert r.status_code == 200
    data = r.get_json()
    assert data["tape_count"] == 3
    assert data["state"] == "waiting"


def test_session_current_no_session(tmp_path):
    client = _make_client(tmp_path)
    r = client.get("/api/session/current")
    assert r.status_code == 404


def test_library_empty(tmp_path):
    client = _make_client(tmp_path)
    r = client.get("/api/library")
    assert r.status_code == 200
    data = r.get_json()
    assert data["tapes"] == []


def test_library_delete(tmp_path):
    client = _make_client(tmp_path)
    from library import save_metadata
    meta = {"filename": "Tape_001.mp4", "base_name": "Tape_001", "duration_seconds": 100}
    save_metadata(str(tmp_path / "output"), "Tape_001", meta)
    r = client.delete("/api/library/Tape_001")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert "Tape_001.json" in data["removed"]


def test_library_delete_not_found(tmp_path):
    client = _make_client(tmp_path)
    r = client.delete("/api/library/nonexistent")
    assert r.status_code == 404
