"""Test config module — provider system."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core import config

def test_preset_providers():
    assert len(config.PRESET_PROVIDERS) >= 5
    ids = [p["id"] for p in config.PRESET_PROVIDERS]
    assert "openai" in ids
    assert "anthropic" in ids
    assert "groq" in ids
    assert "opengateway" in ids

def test_get_all_providers():
    providers = config.get_all_providers()
    assert len(providers) >= 5
    ids = [p["id"] for p in providers]
    assert "openai" in ids

def test_save_and_load_providers():
    # Save custom
    config.save_provider_config("test_provider", api_key="test_key_123")
    loaded = config.load_providers()
    found = [p for p in loaded.get("providers", []) if p.get("id") == "test_provider"]
    assert len(found) == 1
    assert found[0]["api_key"] == "test_key_123"
    # Cleanup
    config.remove_provider("test_provider")

def test_add_custom_provider():
    p = config.add_custom_provider("mytest", "My Test", "https://test.com/v1", "key123", "test-model")
    assert p["id"] == "mytest"
    assert p["name"] == "My Test"
    all_p = config.get_all_providers()
    ids = [x["id"] for x in all_p]
    assert "mytest" in ids
    # Cleanup
    config.remove_provider("mytest")

def test_set_active_provider():
    config.set_active_provider("groq")
    saved = config.load_providers()
    assert saved.get("active") == "groq"
    # Reset
    config.set_active_provider("opengateway")

def test_get_active_config():
    cfg = config.get_active_config()
    assert "base_url" in cfg
    assert "model" in cfg
    assert "api_key" in cfg
    assert "system_prompt" in cfg
    assert "max_tokens" in cfg

def test_get_active_config_has_work_dir_in_prompt():
    cfg = config.get_active_config()
    assert "{work_dir}" not in cfg.get("system_prompt", "")

def test_auto_detect():
    cfg = config.auto_detect()
    assert "default_work_dir" in cfg
    assert "{work_dir}" not in cfg.get("system_prompt", "")

def test_save_and_load_history():
    sid = "test-history-session"
    msgs = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    config.save_history(sid, msgs)
    loaded = config.load_history(sid)
    assert loaded is not None
    assert len(loaded) == 2
    config.delete_history(sid)

def test_load_history_nonexistent():
    assert config.load_history("nonexistent-sid-xyz") is None

def test_delete_history():
    config.save_history("del-test", [{"role": "user", "content": "x"}])
    config.delete_history("del-test")
    assert config.load_history("del-test") is None

def test_list_history():
    config.save_history("list-test-1", [{"role": "user", "content": "a"}])
    history = config.list_history()
    assert len(history) >= 1
    config.delete_history("list-test-1")

def test_cleanup_orphan_history():
    config.save_history("orphan-1", [{"role": "user", "content": "x"}])
    config.save_history("orphan-2", [{"role": "user", "content": "y"}])
    cleaned = config.cleanup_orphan_history(active_chat_ids=["orphan-1"])
    assert cleaned == 1
    assert config.load_history("orphan-1") is not None
    assert config.load_history("orphan-2") is None
    config.delete_history("orphan-1")

def test_remove_provider_auto_switch():
    # Add custom, switch to it, remove it — should auto-switch to opengateway
    config.add_custom_provider("temp-prov", "Temp", "https://t.co/v1", "k", "m")
    config.set_active_provider("temp-prov")
    config.remove_provider("temp-prov")
    saved = config.load_providers()
    assert saved.get("active") == "opengateway"

def test_edit_existing_provider():
    config.save_provider_config("groq", api_key="new-groq-key-123")
    providers = config.get_all_providers()
    groq = [p for p in providers if p["id"] == "groq"][0]
    assert groq["api_key"] == "new-groq-key-123"
    # Restore original
    config.save_provider_config("groq", api_key="")

def test_get_active_config_has_defaults():
    cfg = config.get_active_config()
    assert "base_url" in cfg
    assert "model" in cfg
    assert "api_key" in cfg
    assert "system_prompt" in cfg
    assert "max_tokens" in cfg
    assert "temperature" in cfg

def test_get_active_config_work_dir_injected():
    cfg = config.get_active_config()
    assert "{work_dir}" not in cfg["system_prompt"]

def test_auto_detect():
    cfg = config.auto_detect()
    assert "base_url" in cfg
    assert "default_work_dir" in cfg
    assert "{work_dir}" not in cfg.get("system_prompt", "")

def test_save_and_load_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HIST_DIR", tmp_path)
    config.save_history("chat1", [{"role": "user", "content": "hi"}])
    loaded = config.load_history("chat1")
    assert loaded is not None
    assert loaded[0]["content"] == "hi"

def test_load_history_nonexistent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HIST_DIR", tmp_path)
    assert config.load_history("nope") is None

def test_delete_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HIST_DIR", tmp_path)
    config.save_history("to_del", [{"role": "user", "content": "x"}])
    config.delete_history("to_del")
    assert config.load_history("to_del") is None

def test_cleanup_orphan_history(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "HIST_DIR", tmp_path)
    config.save_history("keep", [{"role": "user", "content": "a"}])
    config.save_history("orphan", [{"role": "user", "content": "b"}])
    cleaned = config.cleanup_orphan_history(["keep"])
    assert cleaned == 1
    assert config.load_history("keep") is not None
    assert config.load_history("orphan") is None

def test_remove_provider_cleans_up():
    config.add_custom_provider("temp_prov", "Temp", "https://t.com/v1", "k", "m")
    config.set_active_provider("temp_prov")
    config.remove_provider("temp_prov")
    saved = config.load_providers()
    assert saved.get("active") == "opengateway"
    ids = [p["id"] for p in saved.get("providers", [])]
    assert "temp_prov" not in ids

def test_default_values():
    assert config.DEFAULTS["max_tokens"] == 16384
    assert config.DEFAULTS["temperature"] == 0.7
    assert config.DEFAULTS["active_provider"] == "opengateway"
    assert config.DEFAULTS["max_rounds"] == 25
