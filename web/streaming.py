"""KEYZBOT streaming chat engine — extracted from server.py."""

import json, time, os, sys
from flask_socketio import emit
from core import config, agent, web_sessions, subagents


def safe_emit(event, data=None, to=None):
    """Emit that silently ignores disconnects — server keeps processing."""
    try:
        if to:
            emit(event, data or {}, to=to)
        else:
            emit(event, data or {})
    except Exception:
        pass


def make_status(bot):
    """Build status dict from bot state."""
    from core import permissions
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


def exec_tool(name, args, work_dir, bot=None):
    """Execute tool using shared router. Intercept spawn_agent for web callbacks."""
    from core import tools as tool_router
    try:
        if name == "spawn_agent":
            atype = args.get("agent_type", "general-purpose")
            agent_name = args.get("name", f"agent-{int(time.time()) % 10000}")
            task = args.get("task", "")
            bg = args.get("background", True)

            def _agent_callback(event_type, data):
                if event_type == "completed":
                    safe_emit("agent_done", {"name": data.get("name"), "result": data.get("result", "")[:500]})
                elif event_type == "failed":
                    safe_emit("agent_error", {"name": data.get("name"), "error": data.get("error", "Unknown")})
                elif event_type == "tool_call":
                    safe_emit("agent_tool_call", data)
                elif event_type == "tool_result":
                    safe_emit("agent_tool_result", data)

            res = subagents.spawn(agent_name, task, atype, bot, work_dir=work_dir, background=bg, callback=_agent_callback)
            if bg:
                return f"Agent '{agent_name}' ({atype}) running in background. Use /agents to check status."
            return res.get("result", "No result")

        return tool_router.execute(name, args, work_dir, bot)
    except Exception as e:
        return f"Error: {e}"


def stream_chat(sid, bot, user_input, chat_id="", images=None, get_browser_id=None, user_sessions=None, streaming_chats=None, stream_buffers=None):
    """Main streaming chat entry point. Runs the agent loop with tool calling."""
    sc = streaming_chats or {}
    key = (sid, chat_id)
    sc[key] = True
    if stream_buffers is not None:
        stream_buffers[key] = {"text": "", "started": False, "done": False}
    try:
        _stream_chat_inner(sid, bot, user_input, chat_id, images=images,
                           get_browser_id=get_browser_id, user_sessions=user_sessions,
                           stream_buffers=stream_buffers, key=key)
    finally:
        sc.pop(key, None)
        if stream_buffers is not None:
            buf = stream_buffers.get(key, {})
            buf["done"] = True


def _stream_chat_inner(sid, bot, user_input, chat_id="", images=None,
                       get_browser_id=None, user_sessions=None,
                       stream_buffers=None, key=None):
    import requests as req
    # Direct connection — bypass system SOCKS5/HTTP proxy
    session = req.Session()
    session.trust_env = False

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

    image_previews = []
    if images:
        for img in images:
            if img.get("dataUrl"):
                image_previews.append(img["dataUrl"])
            elif img.get("b64") and img.get("mime"):
                image_previews.append(f"data:{img['mime']};base64,{img['b64']}")
    safe_emit("chat_start", {"user": user_input, "chat_id": chat_id, "images": image_previews})

    browser_sid = get_browser_id() if get_browser_id else sid
    if user_sessions and browser_sid in user_sessions:
        web_sessions.save_session(browser_sid, user_sessions[browser_sid])

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
        safe_emit("thinking", {"active": True, "chat_id": chat_id})
        try:
            resp = session.post(url, headers=headers, json=body, stream=True, timeout=180)
            if resp.status_code == 413:
                bot._auto_compress()
                body["messages"] = bot.messages
                resp = session.post(url, headers=headers, json=body, stream=True, timeout=180)
                if resp.status_code == 413:
                    body["max_tokens"] = max(512, body["max_tokens"] // 2)
                    msgs = bot.messages
                    sys_msgs = [m for m in msgs if m["role"] == "system"]
                    other_msgs = [m for m in msgs if m["role"] != "system"]
                    bot.messages = sys_msgs + other_msgs[-10:]
                    body["messages"] = bot.messages
                    resp = session.post(url, headers=headers, json=body, stream=True, timeout=180)
            resp.raise_for_status()
        except Exception as e:
            safe_emit("chat_error", {"error": str(e), "chat_id": chat_id})
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
                    safe_emit("bot_stream_start", {"chat_id": chat_id})
                    if stream_buffers and key:
                        stream_buffers[key]["started"] = True
                full_text += content
                if stream_buffers and key:
                    stream_buffers[key]["text"] = full_text
                safe_emit("bot_stream_chunk", {"text": content, "chat_id": chat_id})

            for tc in (delta.get("tool_calls") or []):
                idx = tc.get("index", 0)
                if idx not in tool_calls_buf:
                    tool_calls_buf[idx] = {"id": tc.get("id", ""), "function": {"name": "", "arguments": ""}}
                if tc.get("id"): tool_calls_buf[idx]["id"] = tc["id"]
                if tc.get("function", {}).get("name"): tool_calls_buf[idx]["function"]["name"] = tc["function"]["name"]
                if tc.get("function", {}).get("arguments"): tool_calls_buf[idx]["function"]["arguments"] += tc["function"]["arguments"]

            if finish in ("stop", "tool_calls"): break

        if started:
            safe_emit("bot_stream_end", {"full_text": full_text, "chat_id": chat_id})

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
                safe_emit("tool_call", {"name": fname, "args": json.dumps(fargs, ensure_ascii=False)[:400], "chat_id": chat_id})
                result = exec_tool(fname, fargs, bot.work_dir, bot)
                if isinstance(result, dict) and result.get("type") == "image":
                    safe_emit("tool_result", {"name": fname, "result": f"[Image: {result.get('filename', '?')} ({result.get('size_kb', 0)} KB)]", "chat_id": chat_id})
                    bot.messages.append({
                        "role": "tool", "tool_call_id": tc["id"],
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:{result['mime']};base64,{result['base64']}"}},
                            {"type": "text", "text": f"Image: {result['filename']} ({result['size_kb']} KB)"}
                        ]
                    })
                else:
                    safe_emit("tool_result", {"name": fname, "result": (result or "(no output)")[:3000], "chat_id": chat_id})
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
        safe_emit("chat_done", {"text": full_text, "tokens": bot.tokens, "cost": round(bot.cost, 4), "chat_id": chat_id})
        safe_emit("status", make_status(bot))
        if stream_buffers and key:
            stream_buffers.pop(key, None)
        if user_sessions and browser_sid in user_sessions:
            web_sessions.save_session(browser_sid, user_sessions[browser_sid])
        return

    safe_emit("chat_done", {"text": full_text or "(max rounds)", "tokens": bot.tokens, "cost": round(bot.cost, 4), "chat_id": chat_id})
    safe_emit("status", make_status(bot))
    if stream_buffers and key:
        stream_buffers.pop(key, None)
    if user_sessions and browser_sid in user_sessions:
        web_sessions.save_session(browser_sid, user_sessions[browser_sid])
