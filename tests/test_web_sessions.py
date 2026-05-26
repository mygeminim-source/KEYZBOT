"""Test web_sessions module — persistent session storage."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import web_sessions
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Redirect session store to temp dir."""
    test_file = tmp_path / "web_sessions.json"
    monkeypatch.setattr(web_sessions, "_STORE_FILE", test_file)
    yield test_file


def test_load_sessions_empty():
    sessions = web_sessions.load_sessions()
    assert sessions == {}


def test_save_and_load_session():
    session_data = {
        "chats": {
            "chat1": {"id": "chat1", "name": "Test Chat", "messages": [], "work_dir": "/tmp", "created": "2026-01-01", "messages_count": 0}
        },
        "active_chat": "chat1",
    }
    web_sessions.save_session("browser1", session_data)
    sessions = web_sessions.load_sessions()
    assert "browser1" in sessions
    assert "chat1" in sessions["browser1"]["chats"]


def test_delete_session():
    session_data = {"chats": {"c1": {"id": "c1"}}, "active_chat": "c1"}
    web_sessions.save_session("browser2", session_data)
    web_sessions.delete_session("browser2")
    sessions = web_sessions.load_sessions()
    assert "browser2" not in sessions


def test_delete_chat():
    session_data = {
        "chats": {
            "c1": {"id": "c1", "name": "Chat 1"},
            "c2": {"id": "c2", "name": "Chat 2"},
        },
        "active_chat": "c1",
    }
    web_sessions.save_session("browser3", session_data)
    web_sessions.delete_chat("browser3", "c1")
    sessions = web_sessions.load_sessions()
    assert "c1" not in sessions["browser3"]["chats"]
    assert "c2" in sessions["browser3"]["chats"]


def test_delete_last_chat_removes_session():
    session_data = {"chats": {"only": {"id": "only"}}, "active_chat": "only"}
    web_sessions.save_session("browser4", session_data)
    web_sessions.delete_chat("browser4", "only")
    sessions = web_sessions.load_sessions()
    assert "browser4" not in sessions


def test_get_restored_chats():
    session_data = {
        "chats": {"c1": {"id": "c1", "name": "Restored"}},
        "active_chat": "c1",
    }
    web_sessions.save_session("browser5", session_data)
    chats, active = web_sessions.get_restored_chats("browser5")
    assert "c1" in chats
    assert active == "c1"


def test_get_restored_chats_empty():
    chats, active = web_sessions.get_restored_chats("nonexistent")
    assert chats == {}
    assert active == ""


def test_save_all_sessions():
    sessions = {
        "b1": {"chats": {"c1": {"id": "c1"}}, "active_chat": "c1"},
        "b2": {"chats": {"c2": {"id": "c2"}}, "active_chat": "c2"},
    }
    web_sessions.save_all_sessions(sessions)
    loaded = web_sessions.load_sessions()
    assert "b1" in loaded
    assert "b2" in loaded
