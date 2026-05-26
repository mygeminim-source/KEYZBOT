"""Agent engine — tool-calling loop with hooks, permissions, all tools."""

import json, time, sys, os, requests
from . import ui
from tools.tokenizer import count_tokens as _count_tokens, count_messages_tokens as _count_msg_tokens

_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# ─── Tool Registry ────────────────────────────────────────────────────────────
def _build_tools():
    from tools import bash, file_ops, web, notebook, monitor, image, git_ops, mcp, ask_user, task_tools, cron_tools
    from tools import project_detect, lint_test, github, doc_reader
    tools = [bash.TOOL_DEF]
    tools.extend(file_ops.TOOL_DEFS)
    tools.extend(web.TOOL_DEFS)
    tools.extend(notebook.TOOL_DEFS)
    tools.extend(monitor.TOOL_DEFS)
    tools.extend(image.TOOL_DEFS)
    tools.extend(git_ops.TOOL_DEFS)
    tools.extend(mcp.TOOL_DEFS)
    tools.extend(ask_user.TOOL_DEFS)
    tools.extend(task_tools.TOOL_DEFS)
    tools.extend(cron_tools.TOOL_DEFS)
    tools.extend(project_detect.TOOL_DEFS)
    tools.extend(lint_test.TOOL_DEFS)
    tools.extend(github.TOOL_DEFS)
    tools.extend(doc_reader.TOOL_DEFS)
    # Add agent-level tools
    tools.extend(_AGENT_TOOL_DEFS)
    return tools

# Agent-level tool definitions (memory, plan, agent, skill)
_AGENT_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save information to persistent memory across sessions. Use for remembering user preferences, project context, feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Memory name/identifier"},
                    "content": {"type": "string", "description": "Memory content"},
                    "mtype": {"type": "string", "description": "Type: user, feedback, project, reference"},
                    "scope": {"type": "string", "description": "private or team"}
                },
                "required": ["name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "load_memory",
            "description": "Search or load from persistent memory. Search for past context about users, projects, feedback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term or memory name to load"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_plan",
            "description": "Read the currently active plan file. Use before implementing to check the plan.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan",
            "description": "Update the active plan with notes, exploration findings, or implementation steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "New plan content (replaces existing)"}
                },
                "required": ["content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_agent",
            "description": "Spawn a sub-agent for parallel work. Types: explore (codebase search), plan (architecture), verification (test/check), general-purpose.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Agent name"},
                    "agent_type": {"type": "string", "description": "Type: explore, plan, verification, general-purpose"},
                    "task": {"type": "string", "description": "Task description for the agent"},
                    "background": {"type": "boolean", "description": "Run in background (default true)"}
                },
                "required": ["name", "agent_type", "task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill",
            "description": "Execute a skill (custom slash command). Available: commit, review-pr, simplify, update-config.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "description": "Name of the skill to run"},
                    "args": {"type": "string", "description": "Optional arguments for the skill"}
                },
                "required": ["skill_name"]
            }
        }
    },
]

def _execute_tool(name, args, work_dir=None, bot=None):
    """Route tool call to executor. Returns (result, should_continue)."""
    from . import tools as tool_router, hooks as hooks_mod, permissions as perms

    # Permission check
    perm_result = perms.check(name, args)
    action, reason = perm_result
    if action == "deny":
        return f"Permission denied: {reason}", True
    if action == "confirm":
        args_preview = json.dumps(args, ensure_ascii=False)[:100] if args else ""
        ui.tool_permission(name, args_preview, reason)
        try:
            answer = input(f"  {ui.S.BYLW}?{ui.S.R} Allow {ui.S.BBLU}{name}{ui.S.R}? ({ui.S.BGRN}y{ui.S.R}/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
        if answer == "n":
            return "User denied this tool call", True

    # Pre-tool hooks
    hooks_mod.run_hooks("pre_tool_call", {"tool": name, "args": json.dumps(args or {})})

    # Use shared tool router
    result = tool_router.execute(name, args, work_dir, bot)

    # Post-tool hooks
    hooks_mod.run_hooks("post_tool_call", {"tool": name, "result": result[:200]})

    return result, True

# ─── Smart Engine ─────────────────────────────────────────────────────────────
class Agent:
    # Cost per 1K tokens (input, output) — common models
    MODEL_COSTS = {
        "gpt-4o": (0.0025, 0.01),
        "gpt-4o-mini": (0.00015, 0.0006),
        "gpt-4-turbo": (0.01, 0.03),
        "gpt-3.5-turbo": (0.0005, 0.0015),
        "claude-sonnet-4-20250514": (0.003, 0.015),
        "claude-3-5-haiku": (0.0008, 0.004),
        "claude-3-opus-20240229": (0.015, 0.075),
        "deepseek-chat": (0.00014, 0.00028),
        "deepseek-coder": (0.00014, 0.00028),
        "deepseek-reasoner": (0.00055, 0.00219),
    }

    def __init__(self, cfg):
        self.cfg = cfg
        self.tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost = 0.0
        self.tool_calls_count = 0
        self.work_dir = None
        self.tool_history = []
        self.tools = _build_tools()
        # Build system prompt with work_dir injected
        prompt = cfg.get("system_prompt", "")
        if "{work_dir}" in prompt:
            prompt = prompt.replace("{work_dir}", self.work_dir or "/sdcard/Documents")
        # Inject relevant memories
        memory_context = self._load_memory_context()
        if memory_context:
            prompt += "\n\n## Relevant Memories\n" + memory_context
        # Inject user profile context if available
        profile_ctx = cfg.get("profile_context", "")
        if profile_ctx:
            prompt += profile_ctx
        self.messages = [{"role": "system", "content": prompt}]

    def set_system_prompt(self, prompt):
        # Inject work_dir into prompt if template var present
        if "{work_dir}" in prompt:
            prompt = prompt.replace("{work_dir}", self.work_dir or "/sdcard/Documents")
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = prompt
        else:
            self.messages.insert(0, {"role": "system", "content": prompt})

    def _load_memory_context(self):
        """Load relevant memories for system prompt."""
        try:
            from core import memory
            memory.init()
            mems = memory.list_memories()
            if not mems:
                return ""
            lines = []
            for m in mems[:15]:  # Top 15 memories
                desc = m.get("description", "")
                name = m.get("name", "")
                if desc:
                    lines.append(f"- **{name}**: {desc}")
            return "\n".join(lines) if lines else ""
        except Exception:
            return ""

    def _update_cost(self, input_tokens=0, output_tokens=0):
        """Update token count and cost estimate."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.tokens = self.input_tokens + self.output_tokens
        model = self.cfg.get("model", "")
        costs = self.MODEL_COSTS.get(model, (0.001, 0.003))  # default fallback
        self.cost += (input_tokens / 1000 * costs[0]) + (output_tokens / 1000 * costs[1])

    def get_cost_summary(self):
        """Get formatted cost summary."""
        return f"${self.cost:.4f} ({self.input_tokens}in/{self.output_tokens}out)"

    def clear(self):
        prompt = self.cfg["system_prompt"]
        if "{work_dir}" in prompt:
            prompt = prompt.replace("{work_dir}", self.work_dir or "/sdcard/Documents")
        # Re-inject memories
        memory_context = self._load_memory_context()
        if memory_context:
            prompt += "\n\n## Relevant Memories\n" + memory_context
        # Re-inject user profile context
        profile_ctx = self.cfg.get("profile_context", "")
        if profile_ctx:
            prompt += profile_ctx
        self.messages = [{"role": "system", "content": prompt}]
        self.tokens = 0
        self.tool_history.clear()

    def _call_api(self, stream=True):
        url = f"{self.cfg['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.cfg['api_key']}",
            "Content-Type": "application/json",
        }
        body = {
            "model": self.cfg["model"],
            "messages": self.messages,
            "max_tokens": self.cfg["max_tokens"],
            "temperature": self.cfg["temperature"],
            "stream": stream,
        }
        if self.tools:
            body["tools"] = self.tools
        s = requests.Session()
        s.trust_env = False
        return s.post(url, headers=headers, json=body, stream=stream, timeout=180)

    def _call_api_with_retry(self, stream=True, max_retries=3):
        """Call API with exponential backoff retry for transient errors."""
        import time
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = self._call_api(stream=stream)
                if resp.status_code == 429:
                    wait = min(2 ** attempt * 2, 30)
                    ui.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                if resp.status_code >= 500:
                    wait = min(2 ** attempt, 15)
                    ui.warning(f"Server error {resp.status_code}, retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                return resp
            except requests.exceptions.Timeout:
                last_err = "Request timeout"
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError:
                last_err = "Connection failed"
                time.sleep(2 ** attempt)
            except Exception as e:
                last_err = str(e)
                break
        raise Exception(last_err or "API call failed after retries")

    def _auto_compress(self):
        """Auto-compress context when messages get too large."""
        try:
            total_chars = 0  # fallback for image estimation
            for m in self.messages:
                content = m.get("content", "")
                if isinstance(content, str):
                    total_chars += len(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                total_chars += len(part.get("text", ""))
                            elif part.get("type") == "image_url":
                                total_chars += 500  # estimate for image
                for tc in (m.get("tool_calls") or []):
                    total_chars += len(tc.get("function", {}).get("arguments", ""))
            estimated_tokens = total_chars // 4
            # Also try accurate tokenizer
            try:
                estimated_tokens = max(estimated_tokens, _count_msg_tokens(self.messages))
            except Exception:
                pass
            max_context = self.cfg.get("max_context_tokens", 50000)
            if estimated_tokens < max_context:
                return
            sys_msg = self.messages[0]
            tail = self.messages[-8:]
            middle = self.messages[1:-8]
            if len(middle) < 3:
                return
            summary_parts = []
            for m in middle:
                role = m.get("role", "")
                content = m.get("content", "") or ""
                if role == "tool":
                    if isinstance(content, list):
                        summary_parts.append(f"[tool result]: [multimodal content]")
                    else:
                        summary_parts.append(f"[tool result]: {content[:100]}")
                elif m.get("tool_calls"):
                    names = [tc["function"]["name"] for tc in m["tool_calls"]]
                    summary_parts.append(f"[tool calls]: {', '.join(names)}")
                elif content:
                    summary_parts.append(f"[{role}]: {content[:150]}")
            summary = "[Context auto-compressed]\n" + "\n".join(summary_parts[-20:])
            self.messages = [sys_msg, {"role": "system", "content": summary}] + tail
        except Exception:
            pass

    def chat(self, user_input):
        self.messages.append({"role": "user", "content": user_input})
        ui.user_msg(user_input)

        max_rounds = self.cfg.get("max_rounds", 25)
        for round_num in range(max_rounds):
            if round_num > 0:
                self._auto_compress()
            spinner = ui.Spinner("Thinking")
            spinner.start()

            try:
                resp = self._call_api_with_retry(stream=True)
                resp.raise_for_status()
            except Exception as e:
                spinner.stop()
                err_msg = str(e)
                if "401" in err_msg:
                    ui.error("Invalid API key. Check config.json api_key.")
                elif "429" in err_msg:
                    ui.error("Rate limited. Wait a moment and try again.")
                elif "timeout" in err_msg.lower():
                    ui.error("Request timeout. Server may be overloaded.")
                elif "connection" in err_msg.lower():
                    ui.error("Connection failed. Check base_url and network.")
                else:
                    ui.error(f"API error: {err_msg}")
                self.messages.pop()
                return None

            spinner.stop()

            full_text = ""
            tool_calls = []
            tool_call_buf = {}
            has_content = False
            line_buf = []
            started_label = False
            indent = "    "
            max_content_w = ui.width() - len(indent) - 2

            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line or not raw_line.startswith("data: "):
                    continue
                data = raw_line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices", [])
                if not choices:
                    continue

                delta = choices[0].get("delta", {})
                finish = choices[0].get("finish_reason")

                content = delta.get("content", "")
                if content:
                    if not has_content:
                        has_content = True
                    if not started_label:
                        ui.bot_label()
                        started_label = True
                    for ch in content:
                        if ch == '\n':
                            line_text = "".join(line_buf)
                            rendered = ui._inline(line_text)
                            _sys_write(f"\r\033[K{indent}{rendered}")
                            _sys_write("\n")
                            line_buf.clear()
                        else:
                            line_buf.append(ch)
                    full_text += content

                tc_delta = delta.get("tool_calls", [])
                for tc in tc_delta:
                    idx = tc.get("index", 0)
                    if idx not in tool_call_buf:
                        tool_call_buf[idx] = {"id": tc.get("id", ""), "function": {"name": "", "arguments": ""}}
                    if tc.get("id"):
                        tool_call_buf[idx]["id"] = tc["id"]
                    if tc.get("function", {}).get("name"):
                        tool_call_buf[idx]["function"]["name"] = tc["function"]["name"]
                    if tc.get("function", {}).get("arguments"):
                        tool_call_buf[idx]["function"]["arguments"] += tc["function"]["arguments"]

                if finish in ("stop", "tool_calls"):
                    break

            # Flush remaining
            if line_buf:
                line_text = "".join(line_buf)
                rendered = ui._inline(line_text)
                _sys_write(f"\r\033[K{indent}{rendered}\n")
                line_buf.clear()
            if started_label:
                _sys_write("\n")

            assistant_msg = {"role": "assistant", "content": full_text or None}

            if tool_call_buf:
                tc_list = []
                for idx in sorted(tool_call_buf.keys()):
                    tc = tool_call_buf[idx]
                    tc_list.append({
                        "id": tc["id"] or f"call_{idx}_{int(time.time())}",
                        "type": "function",
                        "function": {"name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                    })
                assistant_msg["tool_calls"] = tc_list
                self.messages.append(assistant_msg)

                for tc in tc_list:
                    func_name = tc["function"]["name"]
                    try:
                        func_args = json.loads(tc["function"]["arguments"])
                    except json.JSONDecodeError:
                        func_args = {}

                    args_preview = json.dumps(func_args, ensure_ascii=False)
                    ui.tool_display(func_name, args_preview[:150], None)

                    result, should_continue = _execute_tool(func_name, func_args, self.work_dir, self)

                    # Display result
                    if isinstance(result, dict) and result.get("type") == "image":
                        ui.tool_display(func_name, f"[Image: {result.get('filename', '?')} ({result.get('size_kb', 0)} KB)]", None)
                    elif result:
                        max_show = 500
                        shown = result[:max_show] if isinstance(result, str) else str(result)[:max_show]
                        if isinstance(result, str) and len(result) > max_show:
                            shown += f"\n... ({len(result) - max_show} chars truncated)"
                        result_lines = shown.strip().split("\n")
                        max_lines = 15
                        for rl in result_lines[:max_lines]:
                            if len(rl) > ui.width() - 8:
                                rl = rl[:ui.width() - 11] + "..."
                            print(f"  {ui.S.D}│{ui.S.R} {rl}")
                        if len(result_lines) > max_lines:
                            print(f"  {ui.S.D}│{ui.S.R} {ui.S.D}... ({len(result_lines) - max_lines} more lines){ui.S.R}")
                        print()

                    # Handle multimodal image results
                    if isinstance(result, dict) and result.get("type") == "image":
                        tool_msg = {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{result['mime']};base64,{result['base64']}"
                                    }
                                },
                                {
                                    "type": "text",
                                    "text": f"Image: {result['filename']} ({result['size_kb']} KB)"
                                }
                            ]
                        }
                        self.messages.append(tool_msg)
                    else:
                        self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result or "(no output)"})
                    self.tool_history.append({"name": func_name, "args": func_args, "result": result})

                continue
            else:
                if full_text:
                    self.messages.append(assistant_msg)
                    output_toks = _count_tokens(full_text)
                    self._update_cost(0, output_toks)
                return full_text

        print(f"\n  {ui.S.BYLW}Max tool rounds ({max_rounds}) reached.{ui.S.R}")
        return full_text if full_text else None


def _sys_write(text):
    sys.stdout.write(text)
    sys.stdout.flush()
