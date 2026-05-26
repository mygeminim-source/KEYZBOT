"""Configuration management for KEYZBOT — multi-provider support."""

import json, os
from pathlib import Path

DIR = Path(__file__).parent.parent
CFG_FILE = DIR / "config.json"
PROVIDERS_FILE = DIR / "providers.json"
HIST_DIR = DIR / "history"

DEFAULT_SYSTEM_PROMPT = """You are KEYZBOT, an autonomous AI coding agent created by WAHYU FAOSZAN MUZAQI. You have FULL filesystem access. You can read, write, and explore ANY directory on the system.

## Filesystem Access
You have complete access to the entire filesystem:
- /sdcard/ — Android external storage (Documents, Downloads, DCIM, etc.)
- /root/ — home directory
- /data/data/com.termux/ — Termux app data
- Any accessible path — use absolute paths freely

Your current working directory is: {work_dir}
Always use absolute paths for reliability. Never assume you're restricted to any single folder.

## Tool Routing Rules
- **Find files**: Use `glob_files` for patterns (e.g. **/*.py), `bash` with `find` for complex queries
- **Search content**: Use `grep_files` for regex search, `bash` with `grep -r` for quick searches
- **Read files**: Use `read_file` (with line numbers), `bash` with `cat` for quick reads
- **Edit files**: Use `edit_file` for precise replacements, `bash` with `sed` for bulk changes
- **Create files**: Use `write_file` for new files
- **Web search**: Use `web_search` for finding info, `web_fetch` for reading pages
- **Shell commands**: Use `bash` for anything tools can't do directly
- **Background tasks**: Use `monitor_start` for long-running processes
- **Images**: Use `read_image` for vision analysis
- **Directories**: Use `list_dir` for quick listing, `bash` with `ls -la` for details

## Behavioral Rules
1. **Batch operations**: When exploring, call multiple tools in parallel (glob + grep + list_dir)
2. **Verify before reporting**: Always check your results — don't report without evidence
3. **Don't repeat context**: If you already read a file, don't read it again
4. **Right-sized execution**: Use the simplest tool that works. Don't over-engineer.
5. **Error recovery**: If a tool fails, analyze WHY and try a different approach
6. **Filesystem hygiene**: No temp files, no duplicates, clean up after tasks
7. **Incremental work**: Small steps, verify each step before proceeding
8. **Be direct**: Short answers for simple tasks, deep reasoning only for complex ones
9. **Auto-detect projects**: When entering a directory, check for package.json, requirements.txt, Cargo.toml, etc.
10. **Smart defaults**: If user asks vague questions, explore broadly first, then narrow down

## When User Asks About Files/Folders
- Start from /sdcard/ or /root/, NOT just the current directory
- Use `list_dir` to explore, then `glob_files` to find patterns
- Show the user what you find — don't assume they know paths

## Context Awareness
- Track your working directory throughout the conversation
- When user says "check my projects" → explore /sdcard/Documents/ broadly
- When user says "fix this code" → read the file first, understand context, then fix
- Always know where you are and what files are nearby"""

DEFAULTS = {
    "base_url": "https://opengateway.gitlawb.com/v1",
    "model": "mimo-v2.5-pro",
    "api_key": "ogw_live_e00b07a96253577cd3933a5bb9bee292",
    "max_tokens": 16384,
    "temperature": 0.7,
    "multimodal_enabled": True,
    "system_prompt": DEFAULT_SYSTEM_PROMPT,
    "active_provider": "opengateway",
    "default_work_dir": "/sdcard/Documents",
    "max_rounds": 25,
    "max_context_tokens": 50000,
}

PRESET_PROVIDERS = [
    {
        "id": "opengateway",
        "name": "OpenGateway",
        "base_url": "https://opengateway.gitlawb.com/v1",
        "models": ["mimo-v2.5-pro", "mimo-v2-flash"],
        "default_model": "mimo-v2.5-pro",
        "api_key": "ogw_live_e00b07a96253577cd3933a5bb9bee292",
        "color": "#10b981",
        "guide_url": "https://opengateway.gitlawb.com",
        "guide_text": "OpenGateway aktif secara default — tidak perlu API key.\nJika ingin pakai key sendiri, bisa generate di situs.",
    },
    {
        "id": "groq",
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
        "default_model": "llama-3.3-70b-versatile",
        "free": True,
        "free_info": "30 RPM, 14,400 RPD",
        "color": "#f97316",
        "guide_url": "https://console.groq.com/keys",
        "guide_text": "1. Buka console.groq.com\n2. Login / daftar (gratis)\n3. menu API Keys → Create API Key\n4. Copy key-nya (gsk_xxx)",
    },
    {
        "id": "sambanova",
        "name": "SambaNova",
        "base_url": "https://api.sambanova.ai/v1",
        "models": ["DeepSeek-V3.1", "DeepSeek-V3.2", "Meta-Llama-3.3-70B-Instruct", "Llama-4-Maverick-17B-128E-Instruct", "gemma-3-12b-it"],
        "default_model": "DeepSeek-V3.1",
        "free": True,
        "free_info": "Free tier, no credit card",
        "color": "#6366f1",
        "guide_url": "https://cloud.sambanova.ai/apis",
        "guide_text": "1. Buka cloud.sambanova.ai\n2. Login / daftar (gratis)\n3. menu API Keys → Generate\n4. Copy key-nya",
    },
    {
        "id": "cerebras",
        "name": "Cerebras",
        "base_url": "https://api.cerebras.ai/v1",
        "models": ["llama3.1-8b", "llama3.1-70b", "llama-3.3-70b"],
        "default_model": "llama3.1-8b",
        "free": True,
        "free_info": "Fast inference, free tier",
        "color": "#ec4899",
        "guide_url": "https://cloud.cerebras.ai/",
        "guide_text": "1. Buka cloud.cerebras.ai\n2. Login / daftar (gratis)\n3. menu API Keys → Create Key\n4. Copy key-nya (csk-xxx)",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["deepseek/deepseek-v4-flash:free", "google/gemma-4-31b-it:free", "nvidia/nemotron-3-super-120b-a12b:free", "qwen/qwen3-next-80b-a3b-instruct:free", "minimax/minimax-m2.5:free"],
        "default_model": "deepseek/deepseek-v4-flash:free",
        "free": True,
        "free_info": "Many free models available",
        "color": "#8b5cf6",
        "guide_url": "https://openrouter.ai/keys",
        "guide_text": "1. Buka openrouter.ai\n2. Login / daftar\n3. menu Keys → Create Key\n4. Copy key-nya (sk-or-xxx)\n5. Pilih model :free untuk gratis",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"],
        "default_model": "deepseek-chat",
        "color": "#0ea5e9",
        "guide_url": "https://platform.deepseek.com/api_keys",
        "guide_text": "1. Buka platform.deepseek.com\n2. Login / daftar\n3. menu API Keys → Create\n4. Copy key-nya (sk-xxx)",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
        "color": "#22c55e",
        "guide_url": "https://platform.openai.com/api-keys",
        "guide_text": "1. Buka platform.openai.com\n2. Login / daftar\n3. menu API Keys → Create\n4. Copy key-nya (sk-xxx)\n5. Perlu billing (bayar)",
    },
    {
        "id": "anthropic",
        "name": "Anthropic (Claude)",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"],
        "default_model": "claude-sonnet-4-20250514",
        "color": "#d97706",
        "guide_url": "https://console.anthropic.com/settings/keys",
        "guide_text": "1. Buka console.anthropic.com\n2. Login / daftar\n3. menu API Keys → Create Key\n4. Copy key-nya (sk-ant-xxx)\n5. Perlu billing (bayar)",
    },
]

# ─── Provider Management ──────────────────────────────────────────────────────

def load_providers():
    """Load saved providers from providers.json."""
    if PROVIDERS_FILE.exists():
        try:
            with open(PROVIDERS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"providers": [], "active": "opengateway"}

def save_providers(data):
    """Save providers to providers.json."""
    DIR.mkdir(parents=True, exist_ok=True)
    with open(PROVIDERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_all_providers():
    """Get all providers (presets + custom)."""
    saved = load_providers()
    all_providers = []
    # Add presets
    for p in PRESET_PROVIDERS:
        provider = dict(p)
        # Check if user has saved API key for this provider
        for sp in saved.get("providers", []):
            if sp.get("id") == p["id"]:
                provider["api_key"] = sp.get("api_key", "")
                provider["base_url"] = sp.get("base_url", p["base_url"])
                provider["model"] = sp.get("model", p["default_model"])
                break
        else:
            provider["api_key"] = p.get("api_key", "")
            provider["model"] = p["default_model"]
        all_providers.append(provider)
    # Add custom providers
    for sp in saved.get("providers", []):
        if sp.get("id") not in [p["id"] for p in PRESET_PROVIDERS]:
            all_providers.append(sp)
    return all_providers

def get_active_provider():
    """Get the currently active provider config."""
    saved = load_providers()
    active_id = saved.get("active", "opengateway")
    providers = get_all_providers()
    for p in providers:
        if p["id"] == active_id:
            return p
    return providers[-1] if providers else None

def set_active_provider(provider_id):
    """Switch active provider."""
    saved = load_providers()
    saved["active"] = provider_id
    save_providers(saved)

def save_provider_config(provider_id, api_key=None, base_url=None, model=None):
    """Save or update a provider's configuration."""
    saved = load_providers()
    found = False
    for p in saved.get("providers", []):
        if p.get("id") == provider_id:
            if api_key is not None:
                p["api_key"] = api_key
            if base_url is not None:
                p["base_url"] = base_url
            if model is not None:
                p["model"] = model
            found = True
            break
    if not found:
        new_p = {"id": provider_id, "api_key": api_key or "", "base_url": base_url or "", "model": model or ""}
        saved.setdefault("providers", []).append(new_p)
    save_providers(saved)

def add_custom_provider(provider_id, name, base_url, api_key, model, models=None):
    """Add a custom provider."""
    saved = load_providers()
    new_p = {
        "id": provider_id,
        "name": name,
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "models": models or [model],
        "default_model": model,
        "custom": True,
    }
    # Remove existing with same id
    saved["providers"] = [p for p in saved.get("providers", []) if p.get("id") != provider_id]
    saved.setdefault("providers", []).append(new_p)
    save_providers(saved)
    return new_p

def remove_provider(provider_id):
    """Remove a custom provider."""
    saved = load_providers()
    saved["providers"] = [p for p in saved.get("providers", []) if p.get("id") != provider_id]
    if saved.get("active") == provider_id:
        saved["active"] = "opengateway"
    save_providers(saved)

# ─── Config (active provider based) ──────────────────────────────────────────

def get_active_config():
    """Get config based on active provider."""
    provider = get_active_provider()
    if not provider:
        cfg = DEFAULTS.copy()
    else:
        cfg = DEFAULTS.copy()
        cfg["base_url"] = provider.get("base_url", DEFAULTS["base_url"])
        cfg["model"] = provider.get("model", DEFAULTS["model"])
        # Fallback: use preset api_key if provider key is empty
        api_key = provider.get("api_key", "")
        if not api_key:
            for preset in PRESET_PROVIDERS:
                if preset["id"] == provider.get("id"):
                    api_key = preset.get("api_key", "")
                    break
        cfg["api_key"] = api_key
        cfg["active_provider"] = provider.get("id", "default")
    # Ensure system_prompt has work_dir injected
    if "{work_dir}" in cfg.get("system_prompt", ""):
        cfg["system_prompt"] = cfg["system_prompt"].replace(
            "{work_dir}", cfg.get("default_work_dir", "/sdcard/Documents"))
    return cfg

# ─── Legacy Compatibility ─────────────────────────────────────────────────────

def load():
    """Load config from file (legacy)."""
    if CFG_FILE.exists():
        with open(CFG_FILE) as f:
            return json.load(f)
    return None

def save(cfg):
    """Save config to file."""
    DIR.mkdir(parents=True, exist_ok=True)
    with open(CFG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def get_or_create():
    """Get config from active provider."""
    return get_active_config()

def save_history(sid, msgs):
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    with open(HIST_DIR / f"{sid}.json", "w") as f:
        json.dump(msgs, f, indent=2)

def load_history(sid):
    p = HIST_DIR / f"{sid}.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None

def delete_history(sid):
    """Delete a single history file."""
    p = HIST_DIR / f"{sid}.json"
    if p.exists():
        p.unlink()

def list_history():
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(HIST_DIR.glob("*.json"), reverse=True)

def cleanup_orphan_history(active_chat_ids):
    """Delete history files that don't match any active chat ID."""
    if not HIST_DIR.exists():
        return 0
    cleaned = 0
    for f in HIST_DIR.glob("*.json"):
        fid = f.stem
        if fid not in active_chat_ids:
            f.unlink()
            cleaned += 1
    return cleaned


def auto_detect():
    """Auto-detect config from environment and return default config."""
    cfg = DEFAULTS.copy()
    # Detect work_dir from environment
    cwd = os.getcwd()
    if os.path.isdir(cwd):
        cfg["default_work_dir"] = cwd
    # Inject work_dir into system prompt
    if "{work_dir}" in cfg.get("system_prompt", ""):
        cfg["system_prompt"] = cfg["system_prompt"].replace("{work_dir}", cfg["default_work_dir"])
    return cfg
