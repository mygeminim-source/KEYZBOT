"""Test memory module — persistent memory CRUD + search."""
import sys, os, tempfile, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import memory
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_memory(tmp_path, monkeypatch):
    """Redirect memory to a temp directory for test isolation."""
    monkeypatch.setattr(memory, "DIR", tmp_path)
    monkeypatch.setattr(memory, "INDEX", tmp_path / "MEMORY.md")
    yield tmp_path


def test_save_and_load():
    path = memory.save("test-mem", "Hello world", mtype="project", scope="private")
    assert path.exists()
    content = memory.load("test-mem")
    assert "Hello world" in content


def test_save_team():
    path = memory.save("team-mem", "Team content", scope="team")
    assert "team" in str(path)
    content = memory.load("team-mem")
    assert "Team content" in content


def test_save_overwrites():
    memory.save("overwrite-test", "version 1")
    memory.save("overwrite-test", "version 2")
    content = memory.load("overwrite-test")
    assert "version 2" in content
    assert "version 1" not in content


def test_load_nonexistent():
    result = memory.load("does-not-exist-xyz")
    assert result is None


def test_list_memories():
    memory.save("mem-a", "Content A")
    memory.save("mem-b", "Content B", scope="team")
    all_mems = memory.list_memories()
    names = [m["name"] for m in all_mems]
    assert len(all_mems) >= 2


def test_list_private_scope():
    memory.save("priv-mem", "Private", scope="private")
    memory.save("team-mem2", "Team", scope="team")
    private = memory.list_memories(scope="private")
    assert all(m["scope"] == "private" for m in private)


def test_search():
    memory.save("searchable", "Python is great for scripting")
    results = memory.search("python")
    assert len(results) >= 1
    assert any("searchable" in r["name"] for r in results)


def test_search_no_match():
    memory.save("unrelated", "nothing here")
    results = memory.search("zzz_nonexistent_zzz")
    assert len(results) == 0


def test_delete():
    memory.save("to-delete", "delete me")
    assert memory.load("to-delete") is not None
    result = memory.delete("to-delete")
    assert result is True
    assert memory.load("to-delete") is None


def test_delete_nonexistent():
    result = memory.delete("no-such-memory-xyz")
    assert result is False


def test_safe_name_sanitization():
    path = memory.save("My Memory! @#$", "content")
    assert path.exists()
    # Should be loadable by sanitized name
    content = memory.load("My Memory! @#$")
    assert content is not None
