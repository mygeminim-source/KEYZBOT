"""Test subagents module."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import subagents

def test_agent_types_exist():
    """Verify all expected agent types are defined."""
    types = subagents.get_types()
    assert "explore" in types
    assert "plan" in types
    assert "verification" in types
    assert "general-purpose" in types

def test_agent_type_has_description():
    types = subagents.get_types()
    for key, val in types.items():
        assert "description" in val
        assert "system_suffix" in val
        assert len(val["system_suffix"]) > 20

def test_active_agents_initially_empty():
    subagents._active_agents.clear()
    subagents._agent_results.clear()
    assert len(subagents._active_agents) == 0
    assert len(subagents._agent_results) == 0
