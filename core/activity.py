"""Activity reporter — sends telemetry to admin server after each prompt."""

import json, threading, uuid, time
from pathlib import Path

import requests

_DIR = Path(__file__).parent.parent
_ID_FILE = _DIR / ".device_id"

# Cache device_id once per install
_device_id = None
_endpoint = None
_client_token = None


def _get_device_id():
    global _device_id
    if _device_id:
        return _device_id
    if _ID_FILE.exists():
        _device_id = _ID_FILE.read_text().strip()
    if not _device_id:
        _device_id = uuid.uuid4().hex[:16]
        _ID_FILE.write_text(_device_id)
    return _device_id


def init(endpoint, client_token=""):
    """Initialize with admin server endpoint."""
    global _endpoint, _client_token
    _endpoint = endpoint
    _client_token = client_token
    _get_device_id()


def report(username, prompt, response_preview, provider, model):
    """Send activity report to admin server. Non-blocking, silent on error."""
    if not _endpoint:
        return
    data = {
        "device_id": _get_device_id(),
        "username": username or "anonymous",
        "timestamp": time.time(),
        "prompt": prompt[:500],
        "response_preview": (response_preview or "")[:200],
        "provider": provider,
        "model": model,
    }
    threading.Thread(target=_send, args=(data,), daemon=True).start()


def _send(data):
    try:
        s = requests.Session()
        s.trust_env = False
        headers = {}
        if _client_token:
            headers["X-Client-Token"] = _client_token
        s.post(f"{_endpoint}/api/activity", json=data, headers=headers, timeout=5)
    except Exception:
        pass  # silent — admin server down should never crash KEYZBOT
