"""KEYZBOT Admin Activity Server — receives telemetry from all KEYZBOT instances."""

import json, os, time, threading
from pathlib import Path
from flask import Flask, request, jsonify, Response
from functools import wraps

DATA_DIR = Path(__file__).parent / "data"
DATA_FILE = DATA_DIR / "activity.json"

ADMIN_KEY = os.environ.get("KEYZBOT_ADMIN_KEY", "")
CLIENT_TOKEN = os.environ.get("KEYZBOT_CLIENT_TOKEN", "")

app = Flask(__name__)

# In-memory activity store
_activities = []
_devices = {}  # device_id -> {last_seen, username, ...}


def _load():
    global _activities, _devices
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATA_FILE.exists():
        try:
            data = json.loads(DATA_FILE.read_text())
            _activities = data.get("activities", [])
            _devices = data.get("devices", {})
        except Exception:
            pass


def _save():
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps({
            "activities": _activities[-2000:],  # keep last 2000
            "devices": _devices,
        }, ensure_ascii=False))
    except Exception:
        pass


def _auto_save():
    while True:
        time.sleep(30)
        _save()


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-Admin-Key") or request.args.get("key", "")
        if not ADMIN_KEY or key != ADMIN_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/activity", methods=["POST"])
def receive_activity():
    if CLIENT_TOKEN:
        token = request.headers.get("X-Client-Token", "")
        if token != CLIENT_TOKEN:
            return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "No data"}), 400

    device_id = data.get("device_id", "unknown")
    entry = {
        "device_id": device_id,
        "username": data.get("username", "anonymous"),
        "timestamp": data.get("timestamp", time.time()),
        "prompt": data.get("prompt", ""),
        "response_preview": data.get("response_preview", ""),
        "provider": data.get("provider", ""),
        "model": data.get("model", ""),
        "received_at": time.time(),
    }
    _activities.append(entry)

    _devices[device_id] = {
        "username": data.get("username", "anonymous"),
        "last_seen": time.time(),
        "provider": data.get("provider", ""),
        "model": data.get("model", ""),
        "last_prompt": data.get("prompt", "")[:100],
    }

    return jsonify({"ok": True})


@app.route("/api/activity", methods=["GET"])
@require_admin
def get_activities():
    since = request.args.get("since", 0, type=float)
    limit = request.args.get("limit", 200, type=int)
    if since:
        items = [a for a in _activities if a["timestamp"] > since]
    else:
        items = _activities[-limit:]
    return jsonify({"activities": items, "devices": _devices})


@app.route("/api/stats", methods=["GET"])
@require_admin
def get_stats():
    now = time.time()
    online = {did: d for did, d in _devices.items() if now - d["last_seen"] < 300}
    today_start = now - (now % 86400)
    today_prompts = [a for a in _activities if a["timestamp"] > today_start]
    return jsonify({
        "total_devices": len(_devices),
        "online_now": len(online),
        "prompts_today": len(today_prompts),
        "total_activities": len(_activities),
    })


@app.route("/admin")
@require_admin
def admin_dashboard():
    return ADMIN_HTML


# SSE stream for real-time updates
@app.route("/api/stream", methods=["GET"])
@require_admin
def stream():
    def generate():
        last = len(_activities)
        while True:
            time.sleep(2)
            if len(_activities) > last:
                new = _activities[last:]
                last = len(_activities)
                for a in new:
                    yield f"data: {json.dumps(a, ensure_ascii=False)}\n\n"
    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>KEYZBOT Activity Monitor</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0a;color:#e0e0e0}
.header{background:#111;border-bottom:1px solid #222;padding:16px 24px;display:flex;justify-content:space-between;align-items:center}
.header h1{font-size:18px;font-weight:600;color:#fff}
.stats{display:flex;gap:24px;padding:16px 24px}
.stat{background:#141414;border:1px solid #222;border-radius:8px;padding:16px 20px;min-width:150px}
.stat .num{font-size:28px;font-weight:700;color:#fff}
.stat .label{font-size:12px;color:#888;margin-top:4px}
.main{display:grid;grid-template-columns:1fr 320px;gap:1px;background:#222;height:calc(100vh - 140px)}
.feed{background:#0a0a0a;overflow-y:auto;padding:12px}
.feed-item{background:#141414;border:1px solid #222;border-radius:8px;padding:12px 16px;margin-bottom:8px}
.feed-item .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}
.feed-item .user{font-weight:600;color:#4fc3f7;font-size:14px}
.feed-item .time{font-size:11px;color:#666}
.feed-item .prompt{font-size:13px;color:#ccc;margin-bottom:6px;line-height:1.4;white-space:pre-wrap;word-break:break-word}
.feed-item .response{font-size:12px;color:#888;border-left:3px solid #333;padding-left:8px;margin-top:6px}
.feed-item .meta{font-size:11px;color:#555;margin-top:6px}
.sidebar{background:#0e0e0e;overflow-y:auto;padding:12px}
.sidebar h2{font-size:14px;color:#888;margin-bottom:12px;font-weight:500}
.user-card{background:#141414;border:1px solid #222;border-radius:8px;padding:10px 12px;margin-bottom:6px}
.user-card .name{font-weight:600;font-size:13px;color:#fff}
.user-card .detail{font-size:11px;color:#666;margin-top:4px}
.online-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#4caf50;margin-right:6px}
.offline-dot{display:inline-block;width:8px;height:8px;border-radius:50;background:#333;margin-right:6px}
.search{width:100%;padding:8px 12px;background:#141414;border:1px solid #333;border-radius:6px;color:#fff;font-size:13px;margin-bottom:12px}
.search:focus{outline:none;border-color:#4fc3f7}
.empty{text-align:center;color:#555;padding:40px;font-size:13px}
</style>
</head>
<body>
<div class="header">
    <h1>KEYZBOT Activity Monitor</h1>
    <div style="font-size:12px;color:#666" id="last-update"></div>
</div>
<div class="stats">
    <div class="stat"><div class="num" id="s-online">0</div><div class="label">Online Now</div></div>
    <div class="stat"><div class="num" id="s-today">0</div><div class="label">Prompts Today</div></div>
    <div class="stat"><div class="num" id="s-total">0</div><div class="label">Total Devices</div></div>
</div>
<div class="main">
    <div class="feed" id="feed">
        <div class="empty">Loading activity...</div>
    </div>
    <div class="sidebar">
        <h2>Users</h2>
        <input class="search" id="search" placeholder="Search users..." oninput="filterUsers()">
        <div id="users"></div>
    </div>
</div>
<script>
const KEY = localStorage.getItem("kbz_admin_key") || prompt("Admin Key:");
if (KEY) localStorage.setItem("kbz_admin_key", KEY);
const headers = {"X-Admin-Key": KEY};

async function loadStats() {
    try {
        const r = await fetch("/api/stats", {headers});
        if (!r.ok) return;
        const d = await r.json();
        document.getElementById("s-online").textContent = d.online_now;
        document.getElementById("s-today").textContent = d.prompts_today;
        document.getElementById("s-total").textContent = d.total_devices;
    } catch {}
}

async function loadActivity() {
    try {
        const r = await fetch("/api/activity?limit=100", {headers});
        if (!r.ok) {document.getElementById("feed").innerHTML='<div class="empty">Unauthorized</div>';return;}
        const d = await r.json();
        renderFeed(d.activities.reverse());
        renderUsers(d.devices);
        document.getElementById("last-update").textContent = new Date().toLocaleTimeString();
    } catch {}
}

function renderFeed(items) {
    const el = document.getElementById("feed");
    if (!items.length) {el.innerHTML='<div class="empty">No activity yet</div>';return;}
    el.innerHTML = items.map(a => `
        <div class="feed-item">
            <div class="top">
                <span class="user">${esc(a.username)}</span>
                <span class="time">${new Date(a.timestamp*1000).toLocaleString()}</span>
            </div>
            <div class="prompt">${esc(a.prompt)}</div>
            ${a.response_preview ? `<div class="response">${esc(a.response_preview)}</div>` : ''}
            <div class="meta">${esc(a.provider)} / ${esc(a.model)}</div>
        </div>
    `).join("");
}

let allDevices = {};
function renderUsers(devices) {
    allDevices = devices;
    filterUsers();
}

function filterUsers() {
    const q = document.getElementById("search").value.toLowerCase();
    const el = document.getElementById("users");
    const now = Date.now()/1000;
    const entries = Object.entries(allDevices).filter(([did,d]) => {
        if (!q) return true;
        return (d.username||"").toLowerCase().includes(q) || did.includes(q);
    }).sort((a,b) => b[1].last_seen - a[1].last_seen);

    if (!entries.length) {el.innerHTML='<div class="empty">No users</div>';return;}
    el.innerHTML = entries.map(([did,d]) => {
        const online = now - d.last_seen < 300;
        const ago = online ? "now" : timeAgo(now - d.last_seen);
        return `<div class="user-card">
            <div class="name"><span class="${online?'online-dot':'offline-dot'}"></span>${esc(d.username||did)}</div>
            <div class="detail">Last: ${ago} &middot; ${esc(d.provider)} &middot; ${esc(d.model)}</div>
            <div class="detail">${esc(d.last_prompt||'')}</div>
        </div>`;
    }).join("");
}

function timeAgo(sec) {
    if (sec < 60) return Math.floor(sec)+"s ago";
    if (sec < 3600) return Math.floor(sec/60)+"m ago";
    if (sec < 86400) return Math.floor(sec/3600)+"h ago";
    return Math.floor(sec/86400)+"d ago";
}

function esc(s) {
    if (!s) return "";
    return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

// SSE for real-time
function connectSSE() {
    const es = new EventSource("/api/stream?key="+KEY);
    es.onmessage = (e) => {
        try {
            const a = JSON.parse(e.data);
            const feed = document.getElementById("feed");
            const first = feed.querySelector(".empty");
            if (first) first.remove();
            const div = document.createElement("div");
            div.className = "feed-item";
            div.innerHTML = `
                <div class="top">
                    <span class="user">${esc(a.username)}</span>
                    <span class="time">${new Date(a.timestamp*1000).toLocaleString()}</span>
                </div>
                <div class="prompt">${esc(a.prompt)}</div>
                ${a.response_preview ? `<div class="response">${esc(a.response_preview)}</div>` : ''}
                <div class="meta">${esc(a.provider)} / ${esc(a.model)}</div>
            `;
            feed.insertBefore(div, feed.firstChild);
            // Update device
            if (allDevices[a.device_id]) {
                allDevices[a.device_id].last_seen = a.timestamp;
                allDevices[a.device_id].last_prompt = (a.prompt||"").substring(0,100);
                renderUsers(allDevices);
            }
        } catch {}
    };
    es.onerror = () => { setTimeout(connectSSE, 5000); es.close(); };
}

loadStats(); loadActivity(); connectSSE();
setInterval(loadStats, 10000);
setInterval(loadActivity, 60000);
</script>
</body>
</html>"""


_load()
threading.Thread(target=_auto_save, daemon=True).start()


def start_admin(port=5050):
    print(f"\033[96m[ADMIN] Activity monitor running at http://localhost:{port}/admin\033[0m")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5050
    start_admin(port)
