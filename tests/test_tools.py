"""Test core tools module."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import tools

def test_get_all_tool_names():
    names = tools.get_all_tool_names()
    assert "bash" in names
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "glob_files" in names
    assert "grep_files" in names
    assert "web_search" in names
    assert "web_fetch" in names
    assert "git" in names
    assert len(names) >= 20

def test_execute_bash():
    result = tools.execute("bash", {"command": "echo hello"})
    assert "hello" in result

def test_execute_unknown():
    result = tools.execute("nonexistent_tool", {})
    assert "Unknown" in result

def test_execute_glob():
    result = tools.execute("glob_files", {"pattern": "*.py", "head_limit": 5})
    assert "file(s)" in result or "No files" in result

def test_execute_grep():
    result = tools.execute("grep_files", {"pattern": "import", "include": "*.py", "output_mode": "count"})
    assert "match" in result

def test_execute_read_file():
    result = tools.execute("read_file", {"path": os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")})
    assert "flask" in result.lower() or "requests" in result.lower()

def test_execute_read_nonexistent():
    result = tools.execute("read_file", {"path": "/tmp/nonexistent_keyzbot_file.xyz"})
    assert "not found" in result.lower() or "error" in result.lower() or "No such" in result

def test_execute_list_dir():
    result = tools.execute("list_dir", {"path": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))})
    assert "file" in result.lower() or "dir" in result.lower() or "item" in result.lower() or "keyzbot" in result.lower()

def test_tool_count():
    names = tools.get_all_tool_names()
    # Should have at least 25 tools
    assert len(names) >= 25

def test_execute_write_and_read(tmp_path):
    test_file = str(tmp_path / "test_write.txt")
    result = tools.execute("write_file", {"path": test_file, "content": "hello test"})
    assert "wrote" in result.lower() or "written" in result.lower() or "success" in result.lower() or "error" not in result.lower()
    content = tools.execute("read_file", {"path": test_file})
    assert "hello test" in content

def test_execute_edit_file(tmp_path):
    test_file = str(tmp_path / "test_edit.txt")
    with open(test_file, "w") as f:
        f.write("old content here")
    result = tools.execute("edit_file", {"path": test_file, "old_string": "old content", "new_string": "new content"})
    with open(test_file) as f:
        assert "new content" in f.read()

def test_execute_list_dir():
    """Test that list_dir returns content."""
    result = tools.execute("list_dir", {"path": os.path.dirname(os.path.dirname(os.path.abspath(__file__)))})
    assert isinstance(result, str) and len(result) > 0

def test_save_memory():
    result = tools.execute("save_memory", {"name": "test-tool-mem", "content": "test content from tool", "mtype": "project"})
    assert "saved" in result.lower() or "memory" in result.lower()

def test_load_memory():
    tools.execute("save_memory", {"name": "load-test-mem", "content": "loadable content"})
    result = tools.execute("load_memory", {"query": "load-test-mem"})
    assert "loadable content" in result

def test_read_plan():
    result = tools.execute("read_plan", {})
    assert isinstance(result, str)

def test_all_tool_names_present():
    """Verify all expected tool categories are registered."""
    names = tools.get_all_tool_names()
    expected = ["bash", "read_file", "write_file", "edit_file", "glob_files", "grep_files",
                "web_search", "web_fetch", "git", "read_image", "mcp_list", "ask_user",
                "detect_project", "lint", "github", "read_document"]
    for name in expected:
        assert name in names, f"Missing tool: {name}"
