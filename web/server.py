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

# Global: disable system proxy for ALL requests sessions (prevents SOCKS crash)
import requests as _req
_orig_session_init = _req.Session.__init__
def _patched_session_init(self, *args, **kwargs):
    _orig_session_init(self, *args, **kwargs)
    self.trust_env = False
_req.Session.__init__ = _patched_session_init

# Force threading mode — eventlet is incompatible with Python 3.14+
# It causes infinite recursion in importlib._bootstrap due to monkey_patch
ASYNC_MODE = "threading"

from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room, join_room
from core import config, agent, memory, plan, tasks, hooks, skills, scheduler, subagents, permissions
from core import web_sessions, rate_limit
from web.terminal import get_terminal, close_terminal
from web.commands import handle_command
from web import profile as _profile

_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=os.path.join(_DIR, "static"), static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("KEYZBOT_SECRET", os.urandom(24).hex())
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=ASYNC_MODE)

# Wire up socketio to streaming module for room-based emits
from web.streaming import set_socketio
set_socketio(socketio)

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
# Accumulated partial text during streaming (for reconnect recovery)
_stream_buffers = {}  # (browser_id, chat_id) -> {"text": str, "started": bool, "done": bool}
_SESSION_TTL = 3600  # 1 hour

# ─── User Profile ────────────────────────────────────────────────────────────
_load_profile = _profile.load
_save_profile = _profile.save
_get_profile_context = _profile.get_context
_enrich_config = _profile.enrich_config

@socketio.on("get_profile")
def on_get_profile():
    emit("profile_data", _profile.load())

@socketio.on("save_profile")
def on_save_profile(data):
    p = _profile.load()
    if data.get("name"):
        p["name"] = data["name"].strip()
    if data.get("birthdate"):
        p["birthdate"] = data["birthdate"].strip()
    if data.get("language"):
        p["language"] = data["language"]
    p["setup_complete"] = True
    _profile.save(p)
    emit("profile_saved", p)
    bid = _get_browser_id()
    user = _user_sessions.get(bid)
    if user:
        emit("chats_updated", {"chats": _make_chat_summary(user), "profile": p})

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
    if response.mimetype in ("text/html", "text/css", "application/javascript", "text/javascript", "image/svg+xml"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

import mimetypes
@app.route("/media/<path:filepath>")
def serve_media(filepath):
    """Serve generated media files (audio, images, video)."""
    media_dir = os.path.join(os.path.expanduser("~"), ".keyzbot", "media")
    full_path = os.path.join(media_dir, filepath)
    if not os.path.isfile(full_path):
        return "Not found", 404
    mime = mimetypes.guess_type(full_path)[0] or "application/octet-stream"
    response = send_from_directory(media_dir, filepath)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response

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
    # Join browser_id room so safe_emit can reach this client after reconnect
    join_room(bid)
    _get_user(bid)
    join_room(bid)
    _start_cron()
    user = _user_sessions[bid]
    # Build messages for active chat
    messages = []
    active_chat = user["chats"].get(user["active_chat"])
    if active_chat:
        bot = active_chat.get("agent")
        if bot:
            messages = _build_messages_for_ui(bot)
    # Check if active chat is currently streaming — restore thinking/partial text
    key = (bid, user["active_chat"])
    is_streaming = key in _streaming_chats
    buf = _stream_buffers.get(key, {})
    emit("connected", {
        "version": "9.1",
        "chats": _make_chat_summary(user),
        "active_chat": user["active_chat"],
        "messages": messages,
        "streaming": is_streaming,
        "stream_text": buf.get("text", ""),
        "stream_done": buf.get("done", False),
        "profile": _load_profile(),
        "update_available": _update_available,
        "latest_commit": _latest_commit,
    })

@socketio.on("disconnect")
def on_disconnect():
    close_terminal(request.sid)
    bid = _get_browser_id()
    leave_room(bid)
    if bid in _user_sessions:
        web_sessions.save_session(bid, _user_sessions[bid])
        # Don't remove session if any chat is still streaming
        has_streaming = any(k[0] == bid for k in _streaming_chats)
        if not has_streaming:
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

    # Check API key
    if not bot.cfg.get("api_key"):
        emit("chat_error", {"error": "No API key configured. Open Settings (⚙) and add your API key for the active provider.", "chat_id": user["active_chat"]})
        return

    # Auto-name chat from first message
    if chat["messages_count"] == 0 and not text.startswith("/"):
        chat["name"] = text[:40] + ("..." if len(text) > 40 else "")

    if text.startswith("/"):
        cmd = text.split()[0].lower()
        result = handle_command(sid, bot, text)

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

        emit("status", make_status(bot))
        emit("chats_updated", {"chats": _make_chat_summary(user)})
        return

    # Guard: don't allow new message while this chat is already streaming
    stream_key = (sid, user["active_chat"])
    if stream_key in _streaming_chats:
        emit("chat_error", {"error": "Please wait — the current response is still being generated.", "chat_id": user["active_chat"]})
        return

    stream_chat(sid, bot, text, user["active_chat"], images=images,
                get_browser_id=_get_browser_id, user_sessions=_user_sessions,
                streaming_chats=_streaming_chats, stream_buffers=_stream_buffers)
    chat["messages_count"] += 1
    web_sessions.save_session(sid, user)
    emit("chats_updated", {"chats": _make_chat_summary(user)})

@socketio.on("file_upload")
def on_file_upload(data):
    sid = request.sid
    if not rate_limit.check_upload_limit(sid):
        remaining = rate_limit.get_remaining(sid)
        emit("upload_result", {"error": f"Rate limit exceeded. {remaining} remaining."})
        return
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
    emit("status", make_status(bot))

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
    s = req.Session()
    s.trust_env = False
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
        resp = s.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept-Encoding": "identity"},
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



# ─── Streaming Chat (imported from streaming.py) ─────────────────────────────
from web.streaming import safe_emit, make_status, exec_tool, stream_chat


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
