"""KEYZBOT Web Server — Flask + SocketIO, all features."""

import sys, os, json, time, threading, uuid, signal, subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_update_available = False
_latest_commit = ""

def _git_check():
    """Check if remote has newer commits. Returns (behind: bool, short_hash: str)."""
    if not os.path.isdir(os.path.join(_REPO_DIR, ".git")):
        return False, ""
    try:
        subprocess.run(["git", "fetch", "--quiet"], cwd=_REPO_DIR,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        remote = subprocess.run(["git", "rev-parse", "@{u}"], cwd=_REPO_DIR,
                                capture_output=True, text=True, timeout=10).stdout.strip()
        if not remote or local == remote:
            return False, ""
        short = subprocess.run(["git", "rev-parse", "--short", remote], cwd=_REPO_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        return True, short
    except Exception:
        return False, ""

def _git_pull_restart():
    """Pull latest changes and restart the server process."""
    try:
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        result = subprocess.run(["git", "pull", "--ff-only", "--quiet"], cwd=_REPO_DIR,
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            req_result = subprocess.run(["git", "diff", "--name-only", local, "HEAD"],
                                        cwd=_REPO_DIR, capture_output=True, text=True, timeout=10)
            if "requirements.txt" in req_result.stdout:
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                               cwd=_REPO_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            print(f"\033[93m[KEYZBOT] Updated! Restarting server...\033[0m")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass

# Set recursion limit higher for complex tool chains
sys.setrecursionlimit(2000)

# Force threading mode — eventlet is incompatible with Python 3.14+
# It causes infinite recursion in importlib._bootstrap due to monkey_patch
ASYNC_MODE = "threading"

from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit
from core import config, agent, memory, plan, tasks, hooks, skills, scheduler, subagents, permissions
from core import web_sessions, rate_limit
from web.terminal import get_terminal, close_terminal

_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(_DIR, "static"), static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("KEYZBOT_SECRET", os.urandom(24).hex())
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE)

# ─── Auth ────────────────────────────────────────────────────────────────────
_AUTH_TOKEN = os.environ.get("KEYZBOT_TOKEN", "")  # Set to enable auth
_authenticated_sids = set()

@socketio.on("authenticate")
def on_authenticate(data):
    sid = _get_browser_id()
    token = data.get("token", "")
    if not _AUTH_TOKEN or token == _AUTH_TOKEN:
        _authenticated_sids.add(sid)
        emit("auth_ok", {"message": "Authenticated"})
    else:
        emit("auth_fail", {"message": "Invalid token"})

def _require_auth(sid):
    """Check if session is authenticated."""
    if not _AUTH_TOKEN:
        return True  # No auth required
    return sid in _authenticated_sids

# ─── Session Store ────────────────────────────────────────────────────────────
# Each browser session gets multiple chat sessions
_user_sessions = {}  # browser_sid -> {chats: {chat_id: {...}}, active_chat: str, last_active: float}
_MAX_SESSIONS = 50
# Track which chats are currently streaming (for reconnect recovery)
_streaming_chats = {}  # (browser_id, chat_id) -> True
_SESSION_TTL = 3600  # 1 hour

# ─── User Profile ────────────────────────────────────────────────────────────
_PROFILE_FILE = os.path.join(os.path.dirname(_DIR), "data", "profile.json")

def _load_profile():
    try:
        with open(_PROFILE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"name": "", "birthdate": "", "language": "id", "setup_complete": False}

def _save_profile(data):
    os.makedirs(os.path.dirname(_PROFILE_FILE), exist_ok=True)
    with open(_PROFILE_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def _get_profile_context():
    """Build user profile context for system prompt injection."""
    p = _load_profile()
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

def _enrich_config(cfg):
    """Add profile context to agent config."""
    if cfg:
        cfg["profile_context"] = _get_profile_context()
    return cfg

@socketio.on("get_profile")
def on_get_profile():
    emit("profile_data", _load_profile())

@socketio.on("save_profile")
def on_save_profile(data):
    profile = _load_profile()
    if data.get("name"):
        profile["name"] = data["name"].strip()
    if data.get("birthdate"):
        profile["birthdate"] = data["birthdate"].strip()
    if data.get("language"):
        profile["language"] = data["language"]
    profile["setup_complete"] = True
    _save_profile(profile)
    emit("profile_saved", profile)
    # Update sidebar with user name
    bid = _get_browser_id()
    user = _user_sessions.get(bid)
    if user:
        emit("chats_updated", {"chats": _make_chat_summary(user), "profile": profile})

def _cleanup_sessions():
    """Remove stale sessions to prevent memory leak."""
    now = time.time()
    stale = [sid for sid, s in _user_sessions.items()
             if now - s.get("last_active", 0) > _SESSION_TTL]
    for sid in stale:
        del _user_sessions[sid]
    # Also enforce max sessions
    if len(_user_sessions) > _MAX_SESSIONS:
        oldest = sorted(_user_sessions, key=lambda s: _user_sessions[s].get("last_active", 0))
        for sid in oldest[:len(_user_sessions) - _MAX_SESSIONS]:
            del _user_sessions[sid]

def _get_user(browser_sid):
    if browser_sid not in _user_sessions:
        # Periodic cleanup
        if len(_user_sessions) > 10:
            _cleanup_sessions()
        # Try to restore from disk
        restored_chats, restored_active = web_sessions.get_restored_chats(browser_sid)
        if restored_chats:
            cfg = _enrich_config(config.get_or_create() or config.DEFAULTS.copy())
            default_wd = cfg.get("default_work_dir", "/sdcard/Documents")
            memory.init()
            chats = {}
            for cid, chat_data in restored_chats.items():
                bot = agent.Agent(cfg)
                bot.work_dir = chat_data.get("work_dir", default_wd) if os.path.isdir(chat_data.get("work_dir", "")) else default_wd
                bot.messages = chat_data.get("messages", [])
                bot.tokens = sum(len(str(m.get("content", "") or "")) for m in bot.messages) // 4
                chats[cid] = {
                    "id": cid,
                    "name": chat_data.get("name", "New Chat"),
                    "agent": bot,
                    "work_dir": bot.work_dir,
                    "created": chat_data.get("created", ""),
                    "messages_count": chat_data.get("messages_count", 0),
                }
            active = restored_active if restored_active in chats else list(chats.keys())[0]
            _user_sessions[browser_sid] = {
                "chats": chats,
                "active_chat": active,
                "last_active": time.time(),
            }
        else:
            chat_id = str(uuid.uuid4())[:8]
            cfg = _enrich_config(config.get_or_create() or config.DEFAULTS.copy())
            bot = agent.Agent(cfg)
            default_wd = cfg.get("default_work_dir", "/sdcard/Documents")
            bot.work_dir = default_wd if os.path.isdir(default_wd) else os.getcwd()
            memory.init()
            _user_sessions[browser_sid] = {
                "chats": {
                    chat_id: {
                        "id": chat_id,
                        "name": "New Chat",
                        "agent": bot,
                        "work_dir": bot.work_dir,
                        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "messages_count": 0,
                    }
                },
                "active_chat": chat_id,
                "last_active": time.time(),
            }
    else:
        _user_sessions[browser_sid]["last_active"] = time.time()
    return _user_sessions[browser_sid]

def _get_active_bot(browser_sid):
    user = _get_user(browser_sid)
    return user["chats"][user["active_chat"]]["agent"]

def _get_active_chat(browser_sid):
    user = _get_user(browser_sid)
    return user["chats"][user["active_chat"]]

def _make_chat_summary(user):
    """Return list of chat summaries for sidebar."""
    result = []
    for cid, chat in user["chats"].items():
        result.append({
            "id": cid,
            "name": chat["name"],
            "messages": chat["messages_count"],
            "active": cid == user["active_chat"],
            "created": chat["created"],
        })
    # Sort by created desc
    result.sort(key=lambda x: x["created"], reverse=True)
    return result

_cron_started = False

def _start_cron():
    global _cron_started
    if _cron_started:
        return
    _cron_started = True
    _last_save = [time.time()]

    def _loop():
        while True:
            time.sleep(60)
            try:
                now = time.localtime()
                for job in scheduler.list_jobs():
                    if not job.get("active", True):
                        continue
                    if scheduler.should_fire(job["cron"], now):
                        for sid in _user_sessions:
                            socketio.emit("cron_fire", {"job_id": job["id"], "prompt": job["prompt"]}, to=sid)
                # Periodic session save (every 5 min)
                if time.time() - _last_save[0] > 300 and _user_sessions:
                    web_sessions.save_all_sessions(_user_sessions)
                    _last_save[0] = time.time()
            except Exception:
                pass
    threading.Thread(target=_loop, daemon=True).start()

# ─── Routes ───────────────────────────────────────────────────────────────────
@app.after_request
def _no_cache(response):
    """Disable caching for static files during development."""
    if response.mimetype in ("text/html", "text/css", "application/javascript"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/config")
def api_config():
    cfg = _enrich_config(config.get_or_create() or config.DEFAULTS.copy())
    return jsonify({
        "model": cfg.get("model", ""),
        "temperature": cfg.get("temperature", 0.7),
        "max_tokens": cfg.get("max_tokens", 4096),
        "base_url": cfg.get("base_url", ""),
        "work_dir": os.getcwd(),
        "version": "9.0",
        "perm_mode": permissions.get_mode(),
    })

def _build_messages_for_ui(bot):
    """Extract messages from bot history for UI display, handling multimodal content."""
    messages = []
    for m in bot.messages:
        if m["role"] == "system":
            continue
        if m["role"] == "user":
            content = m.get("content", "")
            images = []
            text = ""
            if isinstance(content, list):
                # Multimodal content — extract text and images
                for part in content:
                    if part.get("type") == "text":
                        text = part.get("text", "")
                    elif part.get("type") == "image_url":
                        url = part.get("image_url", {}).get("url", "")
                        if url.startswith("data:"):
                            images.append(url)
                messages.append({"type": "user", "text": text, "images": images})
            else:
                messages.append({"type": "user", "text": content or ""})
        elif m["role"] == "assistant":
            content = m.get("content", "")
            if content:
                messages.append({"type": "bot", "text": content})
            tc = m.get("tool_calls")
            if tc:
                for t in tc:
                    messages.append({"type": "tool_call", "name": t["function"]["name"], "args": t["function"]["arguments"][:300]})
        elif m["role"] == "tool":
            messages.append({"type": "tool_result", "text": m.get("content", "")[:2000]})
    return messages

@app.route("/api/export/<fmt>")
def api_export(fmt):
    sid = request.args.get("sid", "")
    user = _user_sessions.get(sid)
    if not user:
        return jsonify({"error": "Session not found"}), 404
    bot = user["chats"][user["active_chat"]]["agent"]
    if fmt == "json":
        return jsonify(bot.messages)
    elif fmt == "text":
        lines = []
        for m in bot.messages:
            if m["role"] == "system": continue
            if m["role"] == "tool":
                lines.append(f"[TOOL]\n{m['content']}\n")
                continue
            tc = m.get("tool_calls")
            if tc:
                for t in tc:
                    lines.append(f"[CALL: {t['function']['name']}]\n{t['function']['arguments']}\n")
                continue
            content = m.get("content", "")
            if content:
                lines.append(f"[{m['role'].upper()}]\n{content}\n")
        return "\n\n".join(lines), 200, {"Content-Type": "text/plain"}
    elif fmt == "markdown":
        lines = ["# KEYZBOT Chat Export\n"]
        for m in bot.messages:
            if m["role"] == "system": continue
            content = m.get("content", "")
            if m["role"] == "user" and content:
                lines.append(f"## User\n{content}\n")
            elif m["role"] == "assistant" and content:
                lines.append(f"## Assistant\n{content}\n")
        return "\n\n".join(lines), 200, {"Content-Type": "text/markdown"}
    return jsonify({"error": "Format: json, text, markdown"}), 400

# ─── SocketIO Events ─────────────────────────────────────────────────────────
def _get_browser_id():
    """Get persistent browser ID from query param, fallback to request.sid."""
    return request.args.get("browser_id", request.sid)

def _get_term_sid():
    """Get the actual Socket.IO session ID for terminal emits."""
    return request.sid

@socketio.on("connect")
def on_connect():
    bid = _get_browser_id()
    if _AUTH_TOKEN and bid not in _authenticated_sids:
        emit("auth_required", {"message": "Token required"})
        return
    _get_user(bid)
    _start_cron()
    user = _user_sessions[bid]
    # Build messages for active chat
    messages = []
    active_chat = user["chats"].get(user["active_chat"])
    if active_chat:
        bot = active_chat.get("agent")
        if bot:
            messages = _build_messages_for_ui(bot)
    # Check if active chat is currently streaming — restore thinking animation
    is_streaming = (bid, user["active_chat"]) in _streaming_chats
    emit("connected", {
        "version": "9.1",
        "chats": _make_chat_summary(user),
        "active_chat": user["active_chat"],
        "messages": messages,
        "streaming": is_streaming,
        "profile": _load_profile(),
        "update_available": _update_available,
        "latest_commit": _latest_commit,
    })

@socketio.on("disconnect")
def on_disconnect():
    close_terminal(request.sid)
    bid = _get_browser_id()
    if bid in _user_sessions:
        web_sessions.save_session(bid, _user_sessions[bid])
        _user_sessions.pop(bid, None)

@socketio.on("new_chat")
def on_new_chat():
    sid = _get_browser_id()
    user = _get_user(sid)
    chat_id = str(uuid.uuid4())[:8]
    cfg = _enrich_config(config.get_or_create() or config.DEFAULTS.copy())
    bot = agent.Agent(cfg)
    default_wd = cfg.get("default_work_dir", "/sdcard/Documents")
    bot.work_dir = default_wd if os.path.isdir(default_wd) else os.getcwd()
    user["chats"][chat_id] = {
        "id": chat_id, "name": "New Chat", "agent": bot,
        "work_dir": bot.work_dir, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "messages_count": 0,
    }
    user["active_chat"] = chat_id
    web_sessions.save_session(sid, user)
    emit("chat_switched", {"chats": _make_chat_summary(user), "active_chat": chat_id})

@socketio.on("switch_chat")
def on_switch_chat(data):
    sid = _get_browser_id()
    user = _get_user(sid)
    chat_id = data.get("chat_id", "")
    if chat_id in user["chats"]:
        user["active_chat"] = chat_id
        bot = user["chats"][chat_id]["agent"]
        messages = _build_messages_for_ui(bot)
        emit("chat_switched", {
            "chats": _make_chat_summary(user),
            "active_chat": chat_id,
            "messages": messages,
        })

@socketio.on("delete_chat")
def on_delete_chat(data):
    sid = _get_browser_id()
    user = _get_user(sid)
    chat_id = data.get("chat_id", "")
    if chat_id in user["chats"]:
        if len(user["chats"]) <= 1:
            # Can't delete last chat — just clear it
            bot = user["chats"][chat_id]["agent"]
            bot.clear()
            user["chats"][chat_id]["name"] = "New Chat"
            user["chats"][chat_id]["messages_count"] = 0
            config.delete_history(chat_id)
            web_sessions.save_session(sid, user)
            emit("chat_deleted", {"chats": _make_chat_summary(user), "active_chat": chat_id, "cleared": True})
            return
        del user["chats"][chat_id]
        if user["active_chat"] == chat_id:
            user["active_chat"] = list(user["chats"].keys())[0]
        config.delete_history(chat_id)
        web_sessions.delete_chat(sid, chat_id)
        # Load messages of the new active chat
        new_active = user["active_chat"]
        messages = []
        if new_active in user["chats"]:
            bot = user["chats"][new_active]["agent"]
            messages = _build_messages_for_ui(bot)
        emit("chat_deleted", {"chats": _make_chat_summary(user), "active_chat": new_active, "messages": messages})

@socketio.on("rename_chat")
def on_rename_chat(data):
    sid = _get_browser_id()
    user = _get_user(sid)
    chat_id = data.get("chat_id", "")
    name = data.get("name", "")
    if chat_id in user["chats"] and name:
        user["chats"][chat_id]["name"] = name
        web_sessions.save_session(sid, user)
        emit("chats_updated", {"chats": _make_chat_summary(user)})

@socketio.on("user_message")
def on_user_message(data):
    sid = _get_browser_id()
    if not _require_auth(sid):
        emit("error", {"message": "Not authenticated"})
        return
    if not rate_limit.check_message_limit(sid):
        remaining = rate_limit.get_remaining(sid)
        emit("chat_error", {"error": f"Rate limit: {remaining} requests remaining. Wait a moment."})
        return
    text = data.get("text", "").strip()
    images = data.get("images", [])
    if not text and not images:
        return
    user = _get_user(sid)
    chat = user["chats"][user["active_chat"]]
    bot = chat["agent"]

    # Auto-name chat from first message
    if chat["messages_count"] == 0 and not text.startswith("/"):
        chat["name"] = text[:40] + ("..." if len(text) > 40 else "")

    if text.startswith("/"):
        cmd = text.split()[0].lower()
        result = _handle_command(sid, bot, text)

        # /clear — reset sidebar chat name and message count, delete history file
        if cmd == "/clear":
            chat["name"] = "New Chat"
            chat["messages_count"] = 0
            config.delete_history(user["active_chat"])

        # Sidebar commands emit ephemeral_result (auto-dismiss, not persisted)
        _EPHEMERAL_CMDS = {"/tools", "/skills", "/agents", "/browse", "/git", "/mcp",
                           "/recall", "/plan", "/tasks", "/hooks", "/cron", "/help",
                           "/config", "/model", "/temp", "/tokens", "/permissions",
                           "/sandbox", "/system"}
        if cmd in _EPHEMERAL_CMDS:
            emit("ephemeral_result", {"text": result, "command": text})
        else:
            emit("command_result", {"text": result, "command": text})

        emit("status", _make_status(bot))
        emit("chats_updated", {"chats": _make_chat_summary(user)})
        return

    _stream_chat(sid, bot, text, user["active_chat"], images=images)
    chat["messages_count"] += 1
    web_sessions.save_session(sid, user)
    emit("chats_updated", {"chats": _make_chat_summary(user)})

@socketio.on("file_upload")
def on_file_upload(data):
    filename = data.get("filename", "")
    b64data = data.get("data", "")
    work_dir = data.get("work_dir", os.getcwd())
    if not filename or not b64data:
        emit("upload_result", {"error": "Missing data"})
        return
    try:
        import base64
        # Sanitize filename — prevent path traversal
        safe_name = os.path.basename(filename).replace("\x00", "")
        if not safe_name:
            emit("upload_result", {"error": "Invalid filename"})
            return
        # Limit file size (10MB for base64)
        if len(b64data) > 14_000_000:  # ~10MB raw after base64
            emit("upload_result", {"error": "File too large (max 10MB)"})
            return
        raw = base64.b64decode(b64data)
        dest = os.path.join(work_dir, safe_name)
        # Ensure destination is within work_dir
        real_dest = os.path.realpath(dest)
        real_work = os.path.realpath(work_dir)
        if not real_dest.startswith(real_work + os.sep) and real_dest != real_work:
            emit("upload_result", {"error": "Path traversal blocked"})
            return
        with open(dest, "wb") as f:
            f.write(raw)
        emit("upload_result", {"path": dest, "size": len(raw), "name": safe_name})
    except Exception as e:
        emit("upload_result", {"error": str(e)})

@socketio.on("ask_answer")
def on_ask_answer(data):
    sid = _get_browser_id()
    user = _get_user(sid)
    user["ask_answer"] = data.get("answer", "")

# ─── Provider Configuration ──────────────────────────────────────────────────
@socketio.on("get_providers")
def on_get_providers():
    providers = config.get_all_providers()
    active = config.get_active_provider()
    emit("providers_data", {
        "providers": providers,
        "active": active.get("id", "") if active else "",
        "presets": config.PRESET_PROVIDERS,
    })

@socketio.on("switch_provider")
def on_switch_provider(data):
    provider_id = data.get("provider_id", "")
    if not provider_id:
        emit("provider_error", {"error": "Missing provider_id"})
        return
    config.set_active_provider(provider_id)
    # Update the active bot's config
    sid = _get_browser_id()
    user = _get_user(sid)
    bot = _get_active_bot(sid)
    cfg = _enrich_config(config.get_active_config())
    bot.cfg = cfg
    # Save API key if provided
    api_key = data.get("api_key", "")
    if api_key:
        config.save_provider_config(provider_id, api_key=api_key)
        bot.cfg["api_key"] = api_key
    emit("provider_switched", {
        "provider_id": provider_id,
        "model": cfg.get("model", ""),
        "base_url": cfg.get("base_url", ""),
    })
    emit("status", _make_status(bot))

@socketio.on("save_provider")
def on_save_provider(data):
    provider_id = data.get("provider_id", "")
    api_key = data.get("api_key", "")
    base_url = data.get("base_url", "")
    model = data.get("model", "")
    if not provider_id:
        emit("provider_error", {"error": "Missing provider_id"})
        return
    config.save_provider_config(provider_id, api_key=api_key or None, base_url=base_url or None, model=model or None)
    emit("provider_saved", {"provider_id": provider_id})

@socketio.on("add_custom_provider")
def on_add_custom_provider(data):
    pid = data.get("id", "").strip().lower().replace(" ", "-")
    name = data.get("name", "").strip()
    base_url = data.get("base_url", "").strip()
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()
    models = data.get("models", [model])
    if not all([pid, name, base_url, model]):
        emit("provider_error", {"error": "ID, Name, URL, and Model are required"})
        return
    provider = config.add_custom_provider(pid, name, base_url, api_key, model, models)
    emit("provider_added", {"provider": provider})

@socketio.on("remove_provider")
def on_remove_provider(data):
    provider_id = data.get("provider_id", "")
    config.remove_provider(provider_id)
    emit("provider_removed", {"provider_id": provider_id})

@socketio.on("test_provider")
def on_test_provider(data):
    """Test a provider connection."""
    import requests as req
    base_url = data.get("base_url", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")
    if not base_url:
        emit("provider_test_result", {"success": False, "error": "Missing base_url"})
        return
    # Use embedded key for OpenGateway if not provided
    if not api_key:
        api_key = "ogw_live_e00b07a96253577cd3933a5bb9bee292"
    if not model:
        model = "mimo-v2.5-pro"
    try:
        resp = req.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
            timeout=15,
        )
        if resp.status_code == 200:
            emit("provider_test_result", {"success": True, "message": "Connection OK"})
        else:
            emit("provider_test_result", {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"})
    except Exception as e:
        emit("provider_test_result", {"success": False, "error": str(e)})

@socketio.on("update_now")
def on_update_now():
    """Pull latest from GitHub and restart server."""
    global _update_available, _latest_commit
    emit("update_status", {"status": "pulling", "message": "Pulling updates..."})
    try:
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_DIR,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        result = subprocess.run(["git", "pull", "--ff-only", "--quiet"], cwd=_REPO_DIR,
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            req_result = subprocess.run(["git", "diff", "--name-only", local, "HEAD"],
                                        cwd=_REPO_DIR, capture_output=True, text=True, timeout=10)
            if "requirements.txt" in req_result.stdout:
                emit("update_status", {"status": "installing", "message": "Installing dependencies..."})
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                               cwd=_REPO_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            emit("update_status", {"status": "restarting", "message": "Restarting server..."})
            _update_available = False
            _latest_commit = ""
            # Give the client time to receive the event
            import time; time.sleep(1)
            print(f"\033[93m[KEYZBOT] Updated by user! Restarting server...\033[0m")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            emit("update_status", {"status": "error", "message": "Update failed. Try manually."})
    except Exception as e:
        emit("update_status", {"status": "error", "message": str(e)})

def _update_checker_loop():
    """Background thread: check for updates every 5 minutes."""
    global _update_available, _latest_commit
    while True:
        time.sleep(300)
        behind, commit = _git_check()
        if behind:
            _update_available = True
            _latest_commit = commit
            socketio.emit("update_available", {"commit": commit})
            print(f"\033[93m[KEYZBOT] Update available: {commit}\033[0m")

def _make_status(bot):
    from core import tools as tool_router
    return {
        "tokens": bot.tokens,
        "input_tokens": bot.input_tokens,
        "output_tokens": bot.output_tokens,
        "cost": round(bot.cost, 4),
        "model": bot.cfg.get("model", ""),
        "work_dir": bot.work_dir or os.getcwd(),
        "perm_mode": permissions.get_mode(),
        "messages": len(bot.messages),
        "tool_count": len(bot.tools),
    }

# ─── Streaming Chat ──────────────────────────────────────────────────────────
def _safe_emit(event, data=None, to=None):
    """Emit that silently ignores disconnects — server keeps processing."""
    try:
        if to:
            emit(event, data or {}, to=to)
        else:
            emit(event, data or {})
    except Exception:
        pass

def _stream_chat(sid, bot, user_input, chat_id="", images=None):
    import requests as req
    # Track streaming state for reconnect recovery
    _streaming_chats[(sid, chat_id)] = True
    try:
        _stream_chat_inner(sid, bot, user_input, chat_id, images=images)
    finally:
        _streaming_chats.pop((sid, chat_id), None)

def _stream_chat_inner(sid, bot, user_input, chat_id="", images=None):
    import requests as req
    # Build user message — multimodal if images present
    if images and len(images) > 0:
        content_parts = []
        if user_input:
            content_parts.append({"type": "text", "text": user_input})
        for img in images:
            if img.get("b64") and img.get("mime"):
                content_parts.append({"type": "image_url", "image_url": {"url": f"data:{img['mime']};base64,{img['b64']}"}})
        bot.messages.append({"role": "user", "content": content_parts})
    else:
        bot.messages.append({"role": "user", "content": user_input})
    # Build images list for UI display (data URLs for preview)
    image_previews = []
    if images:
        for img in images:
            if img.get("dataUrl"):
                image_previews.append(img["dataUrl"])
            elif img.get("b64") and img.get("mime"):
                image_previews.append(f"data:{img['mime']};base64,{img['b64']}")
    _safe_emit("chat_start", {"user": user_input, "chat_id": chat_id, "images": image_previews})
    # Save user message immediately
    browser_sid = _get_browser_id()
    if browser_sid in _user_sessions:
        web_sessions.save_session(browser_sid, _user_sessions[browser_sid])

    url = f"{bot.cfg['base_url']}/chat/completions"
    headers = {"Authorization": f"Bearer {bot.cfg['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": bot.cfg["model"], "messages": bot.messages,
        "max_tokens": bot.cfg["max_tokens"], "temperature": bot.cfg["temperature"], "stream": True,
    }
    if bot.tools:
        body["tools"] = bot.tools

    for _round in range(bot.cfg.get("max_rounds", 25)):
        if _round > 0:
            bot._auto_compress()
            body["messages"] = bot.messages
        _safe_emit("thinking", {"active": True, "chat_id": chat_id})
        try:
            resp = req.post(url, headers=headers, json=body, stream=True, timeout=180)
            # Handle 413 Payload Too Large — compress and retry
            if resp.status_code == 413:
                bot._auto_compress()
                body["messages"] = bot.messages
                resp = req.post(url, headers=headers, json=body, stream=True, timeout=180)
                # If still too large, halve max_tokens and trim oldest messages
                if resp.status_code == 413:
                    body["max_tokens"] = max(512, body["max_tokens"] // 2)
                    # Keep system + last 10 messages
                    msgs = bot.messages
                    sys_msgs = [m for m in msgs if m["role"] == "system"]
                    other_msgs = [m for m in msgs if m["role"] != "system"]
                    bot.messages = sys_msgs + other_msgs[-10:]
                    body["messages"] = bot.messages
                    resp = req.post(url, headers=headers, json=body, stream=True, timeout=180)
            resp.raise_for_status()
        except Exception as e:
            _safe_emit("chat_error", {"error": str(e), "chat_id": chat_id})
            bot.messages.pop()
            return

        full_text = ""
        tool_calls_buf = {}
        started = False

        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data: "): continue
            data = raw_line[6:]
            if data.strip() == "[DONE]": break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices", [])
            if not choices: continue
            delta = choices[0].get("delta", {})
            finish = choices[0].get("finish_reason")

            content = delta.get("content", "")
            if content:
                if not started:
                    started = True
                    _safe_emit("bot_stream_start", {"chat_id": chat_id})
                full_text += content
                _safe_emit("bot_stream_chunk", {"text": content, "chat_id": chat_id})

            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                if idx not in tool_calls_buf:
                    tool_calls_buf[idx] = {"id": tc.get("id", ""), "function": {"name": "", "arguments": ""}}
                if tc.get("id"): tool_calls_buf[idx]["id"] = tc["id"]
                if tc.get("function", {}).get("name"): tool_calls_buf[idx]["function"]["name"] = tc["function"]["name"]
                if tc.get("function", {}).get("arguments"): tool_calls_buf[idx]["function"]["arguments"] += tc["function"]["arguments"]

            if finish in ("stop", "tool_calls"): break

        if started:
            _safe_emit("bot_stream_end", {"full_text": full_text, "chat_id": chat_id})

        assistant_msg = {"role": "assistant", "content": full_text or None}

        if tool_calls_buf:
            tc_list = []
            for idx in sorted(tool_calls_buf.keys()):
                tc = tool_calls_buf[idx]
                tc_list.append({
                    "id": tc["id"] or f"call_{idx}_{int(time.time())}",
                    "type": "function",
                    "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                })
            assistant_msg["tool_calls"] = tc_list
            bot.messages.append(assistant_msg)
            for tc in tc_list:
                fname = tc["function"]["name"]
                try: fargs = json.loads(tc["function"]["arguments"])
                except Exception: fargs = {}
                _safe_emit("tool_call", {"name": fname, "args": json.dumps(fargs, ensure_ascii=False)[:400], "chat_id": chat_id})
                result = _exec_tool(fname, fargs, bot.work_dir, bot)
                # Handle multimodal image results
                if isinstance(result, dict) and result.get("type") == "image":
                    _safe_emit("tool_result", {"name": fname, "result": f"[Image: {result.get('filename', '?')} ({result.get('size_kb', 0)} KB)]", "chat_id": chat_id})
                    bot.messages.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{result['mime']};base64,{result['base64']}"}},
                            {"type": "text", "text": f"Image: {result['filename']} ({result['size_kb']} KB)"}
                        ]
                    })
                else:
                    _safe_emit("tool_result", {"name": fname, "result": (result or "(no output)")[:3000], "chat_id": chat_id})
                    bot.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result or "(no output)"})
            body["messages"] = bot.messages
            continue

        if full_text:
            bot.messages.append(assistant_msg)
            try:
                from tools.tokenizer import count_tokens as _tk_count
                out_toks = _tk_count(full_text)
            except Exception:
                out_toks = len(full_text) // 4
            bot._update_cost(0, out_toks)
        _safe_emit("chat_done", {"text": full_text, "tokens": bot.tokens, "cost": round(bot.cost, 4), "chat_id": chat_id})
        _safe_emit("status", _make_status(bot))
        # Save session so response persists even if client disconnected
        browser_sid = _get_browser_id()
        if browser_sid in _user_sessions:
            web_sessions.save_session(browser_sid, _user_sessions[browser_sid])
        return

    _safe_emit("chat_done", {"text": full_text or "(max rounds)", "tokens": bot.tokens, "cost": round(bot.cost, 4), "chat_id": chat_id})
    _safe_emit("status", _make_status(bot))
    # Save session
    browser_sid = _get_browser_id()
    if browser_sid in _user_sessions:
        web_sessions.save_session(browser_sid, _user_sessions[browser_sid])


def _exec_tool(name, args, work_dir, bot=None):
    """Execute tool using shared router. Intercept spawn_agent for web callbacks."""
    from core import tools as tool_router, subagents
    try:
        # Intercept spawn_agent to add web-compatible callback
        if name == "spawn_agent":
            atype = args.get("agent_type", "general-purpose")
            agent_name = args.get("name", f"agent-{int(time.time()) % 10000}")
            task = args.get("task", "")
            bg = args.get("background", True)

            def _agent_callback(event_type, data):
                """Forward sub-agent events to web UI via Socket.IO."""
                if event_type == "completed":
                    _safe_emit("agent_done", {"name": data.get("name"), "result": data.get("result", "")[:500]})
                elif event_type == "failed":
                    _safe_emit("agent_error", {"name": data.get("name"), "error": data.get("error", "Unknown")})
                elif event_type == "tool_call":
                    _safe_emit("agent_tool_call", data)
                elif event_type == "tool_result":
                    _safe_emit("agent_tool_result", data)

            res = subagents.spawn(agent_name, task, atype, bot, work_dir=work_dir, background=bg, callback=_agent_callback)
            if bg:
                return f"Agent '{agent_name}' ({atype}) running in background. Use /agents to check status."
            return res.get("result", "No result")

        return tool_router.execute(name, args, work_dir, bot)
    except Exception as e:
        return f"Error: {e}"


def _handle_command(sid, bot, text):
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    HELP = ("**KEYZBOT v9.0 Commands**\n\n"
            "**General:** /help /clear /model /temp /tokens /config /system /tools /cd /pwd /setdir /reset /fast /compact\n\n"
            "**Browse:** /browse [path] — show directory tree\n\n"
            "**Memory:** /remember /recall /forget\n\n"
            "**Plan & Tasks:** /plan /tasks\n\n"
            "**Agents:** /fork /agents\n\n"
            "**Export:** /export json|text|markdown\n\n"
            "**Advanced:** /skills /hooks /cron /permissions /sandbox /mcp /git")

    if cmd == "/help": return HELP
    elif cmd == "/clear":
        bot.clear()
        return "Conversation cleared."
    elif cmd == "/model":
        if arg:
            bot.cfg["model"] = arg
            config.save(bot.cfg)
            return f"Model: **{arg}**"
        return f"Model: **{bot.cfg['model']}**"
    elif cmd == "/temp":
        if arg:
            try:
                bot.cfg["temperature"] = max(0, min(2, float(arg)))
                config.save(bot.cfg)
                return f"Temperature: **{bot.cfg['temperature']}**"
            except Exception: return "Invalid number"
        return f"Temperature: **{bot.cfg['temperature']}**"
    elif cmd == "/tokens": return f"Session: **{bot.tokens}** tokens (in:{bot.input_tokens} out:{bot.output_tokens})\nCost: **${bot.cost:.4f}** | Max: **{bot.cfg['max_tokens']}**"
    elif cmd == "/config":
        m = bot.cfg['api_key'][:12] + "..." + bot.cfg['api_key'][-4:] if len(bot.cfg['api_key']) > 16 else "***"
        return f"**URL:** {bot.cfg['base_url']}\n**Model:** {bot.cfg['model']}\n**Temp:** {bot.cfg['temperature']}\n**Tokens:** {bot.cfg['max_tokens']}\n**Key:** {m}\n**Work Dir:** {bot.work_dir}\n**Perm:** {permissions.get_mode()}"
    elif cmd == "/system":
        if arg:
            bot.cfg["system_prompt"] = arg
            config.save(bot.cfg)
            bot.set_system_prompt(arg)
            return "System prompt updated."
        return f"```\n{bot.cfg['system_prompt']}\n```"
    elif cmd == "/tools":
        all_tools = [t["function"]["name"] for t in bot.tools]
        return f"**{len(all_tools)} Tools:**\n" + ", ".join(sorted(all_tools))
    elif cmd == "/cd":
        if arg and os.path.isdir(os.path.expanduser(arg)):
            os.chdir(os.path.expanduser(arg))
            bot.work_dir = os.getcwd()
            return f"Dir: `{bot.work_dir}`"
        return f"Invalid dir: {arg}"
    elif cmd == "/pwd": return f"`{bot.work_dir or os.getcwd()}`"
    elif cmd == "/reset":
        if arg == "confirm":
            cfg = config.auto_detect()
            config.save(cfg)
            return "Config reset."
        return "Type `/reset confirm`"
    elif cmd == "/fast": return "Fast mode toggled."
    elif cmd == "/compact":
        if len(bot.messages) > 4:
            removed = len(bot.messages) - 5
            bot.messages = [bot.messages[0]] + bot.messages[-4:]
            return f"Compacted: removed {removed} messages"
        return "Already compact."
    elif cmd == "/remember":
        if not arg: return "Usage: `/remember <name>: <content>`"
        if ":" in arg:
            n, c = arg.split(":", 1)
            fpath = memory.save(n.strip(), c.strip())
        else:
            fpath = memory.save(arg[:40], arg)
        return f"Saved to `{fpath}`"
    elif cmd == "/recall":
        if arg:
            results = memory.search(arg)
            return "\n".join([f"- **{r['name']}** — {r['description']}" for r in results]) if results else f"No memories for: {arg}"
        mems = memory.list_memories()
        return "\n".join([f"- [{m['type']}] **{m['name']}** — {m['description'][:60]}" for m in mems]) if mems else "No memories saved."
    elif cmd == "/forget": return f"Deleted: {arg}" if arg and memory.delete(arg) else f"Not found: {arg}"
    elif cmd == "/plan":
        if not arg:
            active = plan.get_active()
            if active: return plan.read()[:3000]
            plans_list = plan.list_plans()
            return "\n".join([f"- **{p['title']}** [{p['status']}]" for p in plans_list]) if plans_list else "No plans."
        if arg == "exit":
            path = plan.exit_plan()
            return f"Plan saved: `{path}`" if path else "No active plan."
        return f"Plan created: `{plan.enter(arg)}`"
    elif cmd == "/tasks":
        if not arg:
            all_t = tasks.list_all()
            return "\n".join([f"{'○◉●'[{'pending':0,'in_progress':1,'completed':2}.get(t['status'],0)]} `#{t['id']}` {t['subject']} ({t['status']})" for t in all_t]) if all_t else "No tasks."
        p2 = arg.split(None, 1)
        sub = p2[0].lower()
        if sub == "create" and len(p2) > 1:
            t = tasks.create(p2[1])
            return f"Task `#{t['id']}`: {p2[1]}"
        elif sub == "done" and len(p2) > 1:
            t = tasks.update(p2[1], status="completed")
            return f"Task `#{t['id']}` completed" if t else "Not found"
        elif sub == "start" and len(p2) > 1:
            t = tasks.update(p2[1], status="in_progress")
            return f"Task `#{t['id']}` started" if t else "Not found"
        elif sub == "delete" and len(p2) > 1:
            tasks.delete(p2[1])
            return f"Deleted `#{p2[1]}`"
        return "Usage: /tasks [create|done|start|delete] <id>"
    elif cmd == "/fork":
        if not arg: return "\n".join([f"- **{k}** — {v['description']}" for k, v in subagents.get_types().items()])
        return "Use spawn_agent tool in chat."
    elif cmd == "/agents":
        active = subagents.list_active()
        if not active:
            return "No active agents."
        lines = []
        for n, i in active.items():
            status = i['status']
            if status == "failed" and i.get("error"):
                lines.append(f"- **{n}** [{i['type']}] — **failed**: {i['error']}")
            elif status == "completed" and i.get("result_preview"):
                lines.append(f"- **{n}** [{i['type']}] — completed: {i['result_preview'][:100]}...")
            else:
                lines.append(f"- **{n}** [{i['type']}] — {status}")
        return "\n".join(lines)
    elif cmd == "/skills":
        if arg:
            sk = skills.get_skill(arg)
            return f"```\n{sk.get('prompt','')}\n```" if sk else f"Not found: {arg}"
        return "\n".join([f"- **/{k}** — {v.get('description','')}" for k, v in skills.list_skills().items()])
    elif cmd == "/hooks":
        h = hooks.load_hooks()
        if h: return "\n".join([f"- `{e}`: {hi.get('command','')}" for e, hl in h.items() for hi in hl])
        return "No hooks configured."
    elif cmd == "/cron":
        if not arg:
            jobs = scheduler.list_jobs()
            return "\n".join([f"- `{j['id']}` {j['cron']} — {j['prompt']}" for j in jobs]) if jobs else "No scheduled jobs."
        p2 = arg.split(None, 1)
        if p2[0] == "add" and len(p2) > 1:
            parts3 = p2[1].split(None, 1)
            if len(parts3) >= 2:
                job = scheduler.create(parts3[0], parts3[1])
                return f"Job `#{job['id']}`: {parts3[0]} → {parts3[1][:40]}"
            return "Usage: /cron add <cron> <prompt>"
        elif p2[0] == "del" and len(p2) > 1:
            scheduler.delete(p2[1])
            return f"Job #{p2[1]} deleted"
        return "Usage: /cron [add|del] ..."
    elif cmd == "/permissions":
        if arg and permissions.set_mode(arg): return f"Permission mode: **{arg}**"
        modes = permissions.get_modes()
        cur = permissions.get_mode()
        return "\n".join([f"{'*' if k==cur else ' '} **{k}** — {v}" for k, v in modes.items()])
    elif cmd == "/sandbox":
        if arg and permissions.set_sandbox_mode(arg): return f"Sandbox mode: **{arg}**"
        mode = permissions.get_sandbox_mode()
        info = {"off": "No sandbox (all commands allowed)", "warn": "Warn on dangerous commands", "block": "Block dangerous commands"}
        return "\n".join([f"{'*' if k==mode else ' '} **{k}** — {v}" for k, v in info.items()])
    elif cmd == "/browse":
        from tools import file_ops
        path = arg or bot.work_dir or "/sdcard/Documents"
        path = os.path.expanduser(path)
        return f"```\n{file_ops.execute('tree', {'path': path, 'depth': 2})}\n```"
    elif cmd == "/export": return f"Export: visit /api/export/{arg or 'text'}"
    elif cmd == "/setdir":
        if arg:
            path = os.path.expanduser(arg)
            if os.path.isdir(path):
                bot.cfg["default_work_dir"] = path
                config.save(bot.cfg)
                bot.work_dir = path
                bot.set_system_prompt(bot.cfg["system_prompt"])
                return f"Default dir: `{path}`"
            return f"Not a directory: {arg}"
        return f"Default dir: `{bot.cfg.get('default_work_dir', '/sdcard/Documents')}`"
    elif cmd == "/history":
        from core.config import list_history
        files = list_history()
        return "\n".join([f"- `{f.stem}`" for f in files[:10]]) if files else "No sessions."
    elif cmd == "/load":
        from core.config import load_history
        if arg:
            h = load_history(arg)
            if h:
                bot.messages = h
                return f"Loaded: `{arg}`"
        return "Usage: `/load <id>`"
    elif cmd == "/mcp":
        from tools import mcp
        if arg: return mcp.call_tool(arg.split()[0], arg.split()[1] if len(arg.split()) > 1 else "", {})
        return mcp.list_servers()
    elif cmd == "/git":
        from tools import git_ops
        if not arg: return git_ops.git_status(bot.work_dir)
        p2 = arg.split(None, 1)
        return git_ops.execute("git", {"action": p2[0], "args": p2[1] if len(p2) > 1 else ""}, bot.work_dir)
    elif cmd in ("/exit", "/quit"): return "Close browser tab."
    return f"Unknown: `{cmd}`. Type `/help`."


# ─── Terminal Events (use request.sid — PTY is ephemeral, can't survive refresh) ─
@socketio.on("term_start")
def on_term_start():
    sid = request.sid
    bid = _get_browser_id()
    user = _get_user(bid)
    chat = user["chats"].get(user["active_chat"])
    work_dir = chat["work_dir"] if chat else "/sdcard/Documents"
    get_terminal(sid, socketio, work_dir)
    emit("term_started", {})

@socketio.on("term_input")
def on_term_input(data):
    from web.terminal import _terminals
    if request.sid in _terminals:
        _terminals[request.sid].write(data.get("data", ""))

@socketio.on("term_resize")
def on_term_resize(data):
    from web.terminal import _terminals
    if request.sid in _terminals:
        _terminals[request.sid].resize(data.get("cols", 80), data.get("rows", 24))

@socketio.on("term_stop")
def on_term_stop():
    close_terminal(request.sid)
    emit("term_stopped", {})


def start_web(host="0.0.0.0", port=8080, open_browser=True):
    import webbrowser

    def _shutdown_handler(signum, frame):
        """Graceful shutdown — save state and exit."""
        print("\n  \033[93mShutting down gracefully...\033[0m")
        # Save only chats with actual messages
        for sid, session in _user_sessions.items():
            for cid, chat in session.get("chats", {}).items():
                agent = chat.get("agent")
                if agent and len(agent.messages) > 1:  # >1 because system prompt is always there
                    try:
                        config.save_history(cid, agent.messages)
                    except Exception:
                        pass
        print("  \033[92mState saved. Goodbye!\033[0m")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)
    signal.signal(signal.SIGTERM, _shutdown_handler)

    # Cleanup orphan history files at startup
    def _cleanup_orphans():
        all_chats = set()
        for sid, session in web_sessions.load_sessions().items():
            for cid in session.get("chats", {}).keys():
                all_chats.add(cid)
        cleaned = config.cleanup_orphan_history(all_chats)
        if cleaned > 0:
            print(f"  \033[90mCleaned {cleaned} orphan history file(s)\033[0m")
    threading.Thread(target=_cleanup_orphans, daemon=True).start()

    print()
    print(f"  \033[96m\033[1mKEYZBOT v9.1 Web Terminal\033[0m")
    print(f"  \033[90m{'━' * 40}\033[0m")
    print(f"  \033[92m●\033[0m Server running at \033[97m\033[1mhttp://localhost:{port}\033[0m")
    print(f"  \033[90mPress Ctrl+C to stop\033[0m\n")
    # Start background update checker
    threading.Thread(target=_update_checker_loop, daemon=True).start()
    # Check once at startup
    def _startup_check():
        global _update_available, _latest_commit
        behind, commit = _git_check()
        if behind:
            _update_available = True
            _latest_commit = commit
            print(f"\033[93m[KEYZBOT] Update available: {commit} — will notify clients\033[0m")
    threading.Thread(target=_startup_check, daemon=True).start()

    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_web(port=port)
