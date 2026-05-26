"""Test agent module — tool registry and initialization."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import agent


def test_build_tools_returns_list():
    tools = agent._build_tools()
    assert isinstance(tools, list)
    assert len(tools) >= 30  # 34 tools expected


def test_build_tools_has_bash():
    tools = agent._build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "bash" in names


def test_build_tools_has_file_ops():
    tools = agent._build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "read_file" in names
    assert "write_file" in names
    assert "edit_file" in names
    assert "glob_files" in names
    assert "grep_files" in names


def test_build_tools_has_web():
    tools = agent._build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "web_search" in names
    assert "web_fetch" in names


def test_build_tools_has_agent_tools():
    tools = agent._build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "save_memory" in names
    assert "load_memory" in names
    assert "read_plan" in names
    assert "update_plan" in names
    assert "spawn_agent" in names


def test_build_tools_has_git():
    tools = agent._build_tools()
    names = [t["function"]["name"] for t in tools]
    assert "git" in names


def test_build_tools_format():
    """Each tool should have proper OpenAI function-calling format."""
    tools = agent._build_tools()
    for t in tools:
        assert "type" in t
        assert t["type"] == "function"
        assert "function" in t
        func = t["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func


def test_agent_init():
    cfg = {
        "base_url": "https://test.com/v1",
        "model": "test-model",
        "api_key": "test-key",
        "max_tokens": 1000,
        "temperature": 0.5,
        "system_prompt": "You are a test agent.",
        "max_rounds": 5,
        "max_context_tokens": 10000,
    }
    bot = agent.Agent(cfg)
    assert bot.cfg["model"] == "test-model"
    assert len(bot.messages) == 1  # system prompt
    assert bot.messages[0]["role"] == "system"
    assert bot.tokens == 0
    assert bot.cost == 0.0


def test_agent_tool_defs_structure():
    for tool_def in agent._AGENT_TOOL_DEFS:
        assert "type" in tool_def
        assert tool_def["type"] == "function"
        func = tool_def["function"]
        assert "name" in func
        assert "description" in func
