"""Sub-agents — fork/spawn specialized agents with shared context."""

import json, time, threading, os, sys, requests

# Agent types matching OpenClaude
AGENT_TYPES = {
    "explore": {
        "description": "Fast agent for codebase exploration — file search, code search, understanding architecture",
        "system_suffix": """You are an Explore agent. Your job is to quickly find and report information about the codebase.
Use glob_files, grep_files, read_file, list_dir, tree to explore. Be thorough but concise.
Report findings in under 200 words unless asked for detail.
Always use absolute paths starting from /sdcard or /root.""",
    },
    "plan": {
        "description": "Software architect — design implementation plans before coding",
        "system_suffix": """You are a Plan agent. Your job is to design implementation strategies.
Explore the codebase, understand patterns, identify critical files, and produce step-by-step plans.
Use read_file, glob_files, grep_files, tree to understand the code. Do NOT edit or write files.
Always use absolute paths starting from /sdcard or /root.""",
    },
    "verification": {
        "description": "Verify implementation correctness — run tests, checks, linters",
        "system_suffix": """You are a Verification agent. Your job is to verify that implementation work is correct.
Run builds, tests, linters, and checks. Produce a PASS/FAIL/PARTIAL verdict with evidence.
If PASS: spot-check 2-3 commands from the report.""",
    },
    "general-purpose": {
        "description": "General agent for research, code search, multi-step tasks",
        "system_suffix": """You are a General-purpose agent. Handle the task autonomously.
You have access to all tools. Research thoroughly, implement carefully.
Always use absolute paths starting from /sdcard or /root.""",
    },
}

# Track active agents
_active_agents = {}  # name -> info dict
_agent_results = {}  # name -> result string
_agent_callbacks = {}  # name -> callback(event_type, data)

def get_types():
    return AGENT_TYPES

def spawn(name, task, agent_type, agent_engine, work_dir=None, background=False, callback=None):
    """Spawn a sub-agent. Returns immediately if background.

    Args:
        name: Unique agent name
        task: Task description/prompt
        agent_type: One of AGENT_TYPES keys
        agent_engine: Parent agent instance for context
        work_dir: Working directory override
        background: Run in background thread
        callback: Optional function called with (event_type, data) for streaming
    """
    if agent_type not in AGENT_TYPES:
        return {"error": f"Unknown agent type: {agent_type}. Available: {list(AGENT_TYPES.keys())}"}

    type_info = AGENT_TYPES[agent_type]
    suffix = type_info["system_suffix"]

    sub_agent = {
        "name": name,
        "type": agent_type,
        "status": "running",
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "task": task,
    }

    if callback:
        _agent_callbacks[name] = callback

    if background:
        def _run():
            try:
                result = _execute_subagent(name, task, suffix, agent_engine, work_dir)
                _agent_results[name] = result
                _active_agents[name]["status"] = "completed"
                _active_agents[name]["result_preview"] = result[:300] if isinstance(result, str) else str(result)[:300]
                if name in _agent_callbacks:
                    _agent_callbacks[name]("completed", {"name": name, "result": result[:500]})
            except Exception as e:
                err = str(e)
                _agent_results[name] = f"Error: {err}"
                _active_agents[name]["status"] = "failed"
                _active_agents[name]["error"] = err
                if name in _agent_callbacks:
                    _agent_callbacks[name]("failed", {"name": name, "error": err})

        sub_agent["status"] = "running"
        _active_agents[name] = sub_agent
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        return {"name": name, "status": "running", "message": f"Agent '{name}' running in background"}

    # Foreground
    try:
        result = _execute_subagent(name, task, suffix, agent_engine, work_dir)
        _agent_results[name] = result
        return {"name": name, "status": "completed", "result": result}
    except Exception as e:
        _agent_results[name] = f"Error: {e}"
        return {"name": name, "status": "failed", "error": str(e)}

def _execute_subagent(name, task, system_suffix, agent_engine, work_dir):
    """Execute a sub-agent task — web-compatible, no CLI UI dependency."""
    from . import config as cfg_mod

    cfg = cfg_mod.get_or_create()
    if not cfg:
        raise Exception("No config available — check providers.json")

    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "")
    model = cfg.get("model", "")
    if not api_key:
        raise Exception(f"No API key for provider '{cfg.get('active_provider', '?')}' — add key in Provider Settings")
    if not base_url:
        raise Exception("No base_url configured")

    # Build system prompt with parent context
    parent_prompt = cfg.get("system_prompt", "")
    context_section = ""
    if agent_engine and hasattr(agent_engine, "messages"):
        summary = _summarize_parent_context(agent_engine.messages)
        if summary:
            context_section = f"\n\n## Parent Conversation Context\n{summary}"

    system_prompt = parent_prompt + context_section + "\n\n" + system_suffix

    # Inherit work_dir
    wd = work_dir
    if not wd and agent_engine and hasattr(agent_engine, "work_dir"):
        wd = agent_engine.work_dir
    if not wd:
        wd = cfg.get("default_work_dir", "/sdcard/Documents")

    # Build tools list (same as parent)
    from . import agent as agent_mod
    tools = agent_mod._build_tools()

    messages = [{"role": "system", "content": system_prompt}]
    messages.append({"role": "user", "content": task})

    # Notify callback of start
    if name in _agent_callbacks:
        _agent_callbacks[name]("started", {"name": name, "task": task[:200]})

    max_rounds = cfg.get("max_rounds", 25)
    full_text = ""

    for round_num in range(max_rounds):
        # Call API
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "messages": messages,
            "max_tokens": cfg.get("max_tokens", 16384),
            "temperature": cfg.get("temperature", 0.7),
            "stream": False,  # Non-streaming for sub-agents (simpler, more reliable)
        }
        if tools:
            body["tools"] = tools

        try:
            s = requests.Session()
            s.trust_env = False
            resp = s.post(url, headers=headers, json=body, timeout=180)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "?"
            body_text = ""
            try:
                body_text = e.response.text[:300] if e.response else ""
            except Exception:
                pass
            raise Exception(f"API error {status}: {body_text}")
        except requests.exceptions.Timeout:
            raise Exception("API request timeout (180s)")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Connection failed to {base_url}")
        except Exception as e:
            raise Exception(f"API call failed: {e}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise Exception(f"Empty API response: {json.dumps(data)[:200]}")

        message = choices[0].get("message", {})
        content = message.get("content", "") or ""
        tool_calls = message.get("tool_calls") or []

        if content:
            full_text += content
            # Notify callback of content
            if name in _agent_callbacks:
                _agent_callbacks[name]("chunk", {"name": name, "text": content})

        if tool_calls:
            # Process tool calls
            messages.append(message)
            for tc in tool_calls:
                fname = tc.get("function", {}).get("name", "")
                fargs_str = tc.get("function", {}).get("arguments", "{}")
                tc_id = tc.get("id", f"call_{int(time.time())}")

                try:
                    fargs = json.loads(fargs_str)
                except Exception:
                    fargs = {}

                # Notify callback of tool call
                if name in _agent_callbacks:
                    _agent_callbacks[name]("tool_call", {"name": name, "tool": fname, "args": json.dumps(fargs, ensure_ascii=False)[:200]})

                # Execute tool
                try:
                    from . import tools as tool_router
                    result = tool_router.execute(fname, fargs, wd, None)
                except Exception as e:
                    result = f"Tool error: {e}"

                if not result:
                    result = "(no output)"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc_id,
                    "content": result[:5000]  # Truncate large results
                })

                # Notify callback of tool result
                if name in _agent_callbacks:
                    _agent_callbacks[name]("tool_result", {"name": name, "tool": fname, "result": result[:300]})

            continue  # Next round for tool results

        # No tool calls — we're done
        if content:
            messages.append({"role": "assistant", "content": content})
        break

    return full_text or "(no response)"

def _summarize_parent_context(messages):
    """Create a brief summary of parent conversation for subagent context."""
    if not messages or len(messages) < 2:
        return ""

    parts = []
    for m in messages[-6:]:  # Last 6 messages for context
        role = m.get("role", "")
        content = m.get("content", "") or ""

        if role == "system":
            continue
        elif role == "user":
            parts.append(f"User: {content[:150]}")
        elif role == "assistant" and content:
            parts.append(f"Assistant: {content[:150]}")
        elif role == "tool":
            parts.append(f"[Tool result]: {content[:80]}")
        elif m.get("tool_calls"):
            names = [tc["function"]["name"] for tc in m["tool_calls"]]
            parts.append(f"[Tool calls]: {', '.join(names)}")

    return "\n".join(parts[-8:]) if parts else ""

def get_result(name):
    return _agent_results.get(name)

def get_error(name):
    """Get error message for a failed agent."""
    info = _active_agents.get(name)
    if info and info.get("status") == "failed":
        return info.get("error", "Unknown error")
    return None

def list_active():
    result = {}
    for k, v in _active_agents.items():
        info = {"status": v["status"], "type": v["type"], "task": v["task"][:80]}
        if v["status"] == "failed" and v.get("error"):
            info["error"] = v["error"][:200]
        if v["status"] == "completed" and v.get("result_preview"):
            info["result_preview"] = v["result_preview"][:200]
        result[k] = info
    return result

def wait(name, timeout=120):
    """Wait for a background agent to complete."""
    start = time.time()
    while time.time() - start < timeout:
        if name in _agent_results:
            return _agent_results[name]
        time.sleep(0.5)
    return f"Timeout waiting for agent '{name}'"

def cleanup():
    """Clean up completed agents older than 1 hour."""
    now = time.time()
    to_remove = []
    for name, info in _active_agents.items():
        if info["status"] in ("completed", "failed"):
            started = info.get("started", "")
            if started:
                try:
                    t = time.mktime(time.strptime(started, "%Y-%m-%d %H:%M:%S"))
                    if now - t > 3600:
                        to_remove.append(name)
                except Exception:
                    pass
    for name in to_remove:
        _active_agents.pop(name, None)
        _agent_results.pop(name, None)
        _agent_callbacks.pop(name, None)
