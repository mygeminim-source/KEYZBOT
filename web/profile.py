"""User profile management for KEYZBOT web UI."""

import json, os

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROFILE_FILE = os.path.join(_DIR, "data", "profile.json")


def load():
    """Load user profile from disk."""
    try:
        with open(_PROFILE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"name": "", "birthdate": "", "language": "id", "setup_complete": False}


def save(data):
    """Save user profile to disk."""
    os.makedirs(os.path.dirname(_PROFILE_FILE), exist_ok=True)
    with open(_PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_context():
    """Build user profile context string for system prompt injection."""
    p = load()
    if not p.get("setup_complete"):
        return ""
    parts = []
    if p.get("name"):
        parts.append(f"- User name: {p['name']}")
    if p.get("birthdate"):
        parts.append(f"- Born: {p['birthdate']}")
    if p.get("language"):
        lang = "Indonesian" if p["language"] == "id" else "English"
        parts.append(f"- Preferred language: {lang}")
    if not parts:
        return ""
    return "\n\n## User Profile\n" + "\n".join(parts) + "\n- Developer: WAHYU FAOSZAN MUZAQI (creator of KEYZBOT)"


def enrich_config(cfg):
    """Add profile context to agent config."""
    if cfg:
        cfg["profile_context"] = get_context()
    return cfg
