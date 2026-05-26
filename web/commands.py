"""KEYZBOT slash-command handler — extracted from server.py for maintainability."""

import os
from core import config, memory, plan, tasks, hooks, skills, scheduler, subagents, permissions


HELP = ("**KEYZBOT v9.2 Commands**\n\n"
        "**General:** /help /clear /model /temp /tokens /config /system /tools /cd /pwd /setdir /reset /fast /compact\n\n"
        "**Browse:** /browse [path] — show directory tree\n\n"
        "**Memory:** /remember /recall /forget\n\n"
        "**Plan & Tasks:** /plan /tasks\n\n"
        "**Agents:** /fork /agents\n\n"
        "**Export:** /export json|text|markdown\n\n"
        "**Advanced:** /skills /hooks /cron /permissions /sandbox /mcp /git")


def handle_command(sid, bot, text):
    """Process a slash command. Returns markdown response string.

    Args:
        sid: Session/browser ID
        bot: Agent instance
        text: Full command text including the leading /

    Returns:
        Markdown string for display in chat
    """
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd == "/help":
        return HELP
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
            except Exception:
                return "Invalid number"
        return f"Temperature: **{bot.cfg['temperature']}**"
    elif cmd == "/tokens":
        return (f"Session: **{bot.tokens}** tokens (in:{bot.input_tokens} out:{bot.output_tokens})\n"
                f"Cost: **${bot.cost:.4f}** | Max: **{bot.cfg['max_tokens']}**")
    elif cmd == "/config":
        m = bot.cfg['api_key'][:12] + "..." + bot.cfg['api_key'][-4:] if len(bot.cfg['api_key']) > 16 else "***"
        return (f"**URL:** {bot.cfg['base_url']}\n**Model:** {bot.cfg['model']}\n"
                f"**Temp:** {bot.cfg['temperature']}\n**Tokens:** {bot.cfg['max_tokens']}\n"
                f"**Key:** {m}\n**Work Dir:** {bot.work_dir}\n**Perm:** {permissions.get_mode()}")
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
    elif cmd == "/pwd":
        return f"`{bot.work_dir or os.getcwd()}`"
    elif cmd == "/reset":
        if arg == "confirm":
            cfg = config.auto_detect()
            config.save(cfg)
            return "Config reset."
        return "Type `/reset confirm`"
    elif cmd == "/fast":
        return "Fast mode toggled."
    elif cmd == "/compact":
        if len(bot.messages) > 4:
            removed = len(bot.messages) - 5
            bot.messages = [bot.messages[0]] + bot.messages[-4:]
            return f"Compacted: removed {removed} messages"
        return "Already compact."
    elif cmd == "/remember":
        if not arg:
            return "Usage: `/remember <name>: <content>`"
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
    elif cmd == "/forget":
        return f"Deleted: {arg}" if arg and memory.delete(arg) else f"Not found: {arg}"
    elif cmd == "/plan":
        if not arg:
            active = plan.get_active()
            if active:
                return plan.read()[:3000]
            plans_list = plan.list_plans()
            return "\n".join([f"- **{p['title']}** [{p['status']}]" for p in plans_list]) if plans_list else "No plans."
        if arg == "exit":
            path = plan.exit_plan()
            return f"Plan saved: `{path}`" if path else "No active plan."
        return f"Plan created: `{plan.enter(arg)}`"
    elif cmd == "/tasks":
        if not arg:
            all_t = tasks.list_all()
            return "\n".join([f"{'○◉●'[{'pending': 0, 'in_progress': 1, 'completed': 2}.get(t['status'], 0)]} `#{t['id']}` {t['subject']} ({t['status']})" for t in all_t]) if all_t else "No tasks."
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
        if not arg:
            return "\n".join([f"- **{k}** — {v['description']}" for k, v in subagents.get_types().items()])
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
            return f"```\n{sk.get('prompt', '')}\n```" if sk else f"Not found: {arg}"
        return "\n".join([f"- **/{k}** — {v.get('description', '')}" for k, v in skills.list_skills().items()])
    elif cmd == "/hooks":
        h = hooks.load_hooks()
        if h:
            return "\n".join([f"- `{e}`: {hi.get('command', '')}" for e, hl in h.items() for hi in hl])
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
        if arg and permissions.set_mode(arg):
            return f"Permission mode: **{arg}**"
        modes = permissions.get_modes()
        cur = permissions.get_mode()
        return "\n".join([f"{'*' if k == cur else ' '} **{k}** — {v}" for k, v in modes.items()])
    elif cmd == "/sandbox":
        if arg and permissions.set_sandbox_mode(arg):
            return f"Sandbox mode: **{arg}**"
        mode = permissions.get_sandbox_mode()
        info = {"off": "No sandbox (all commands allowed)", "warn": "Warn on dangerous commands", "block": "Block dangerous commands"}
        return "\n".join([f"{'*' if k == mode else ' '} **{k}** — {v}" for k, v in info.items()])
    elif cmd == "/browse":
        from tools import file_ops
        path = arg or bot.work_dir or "/sdcard/Documents"
        path = os.path.expanduser(path)
        return f"```\n{file_ops.execute('tree', {'path': path, 'depth': 2})}\n```"
    elif cmd == "/export":
        return f"Export: visit /api/export/{arg or 'text'}"
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
        if arg:
            return mcp.call_tool(arg.split()[0], arg.split()[1] if len(arg.split()) > 1 else "", {})
        return mcp.list_servers()
    elif cmd == "/git":
        from tools import git_ops
        if not arg:
            return git_ops.git_status(bot.work_dir)
        p2 = arg.split(None, 1)
        return git_ops.execute("git", {"action": p2[0], "args": p2[1] if len(p2) > 1 else ""}, bot.work_dir)
    elif cmd in ("/exit", "/quit"):
        return "Close browser tab."
    return f"Unknown: `{cmd}`. Type `/help`."
