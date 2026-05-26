"""Test hooks module — load, run, add, remove hooks."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import hooks
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Redirect settings file to temp dir."""
    test_settings = tmp_path / "settings.json"
    monkeypatch.setattr(hooks, "SETTINGS", test_settings)
    yield test_settings


def test_load_hooks_empty():
    hooks_data = hooks.load_hooks()
    assert hooks_data == {}


def test_load_hooks_from_file(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"pre_tool_call": [{"command": "echo hi"}]}}))
    hooks_data = hooks.load_hooks()
    assert "pre_tool_call" in hooks_data


def test_add_hook():
    hooks.add_hook("pre_tool_call", "echo test")
    hooks_data = hooks.load_hooks()
    assert "pre_tool_call" in hooks_data
    assert any(h["command"] == "echo test" for h in hooks_data["pre_tool_call"])


def test_run_hooks_no_match():
    results = hooks.run_hooks("nonexistent_event")
    assert results == []


def test_run_hooks_echo():
    hooks.add_hook("post_response", "echo hello")
    results = hooks.run_hooks("post_response")
    assert len(results) == 1
    assert "hello" in results[0]["stdout"]
    assert results[0]["returncode"] == 0


def test_run_hooks_with_context():
    hooks.add_hook("test_event", "echo {msg}")
    results = hooks.run_hooks("test_event", {"msg": "world"})
    assert len(results) == 1
    assert "world" in results[0]["stdout"]


def test_remove_hooks_event():
    hooks.add_hook("to_remove", "echo rm")
    hooks.remove_hooks("to_remove")
    hooks_data = hooks.load_hooks()
    assert "to_remove" not in hooks_data


def test_remove_all_hooks():
    hooks.add_hook("event1", "echo 1")
    hooks.add_hook("event2", "echo 2")
    hooks.remove_hooks()
    hooks_data = hooks.load_hooks()
    assert hooks_data == {}
