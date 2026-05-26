#!/usr/bin/env python3
"""
KEYZBOT v9.0 - Full AI Coding Agent CLI
Created by KEYZ — Feature-complete like OpenClaude
"""

import sys, os, time, json, threading, subprocess

def _auto_update():
    """Check GitHub for updates, pull and restart if newer version exists."""
    repo_dir = os.path.dirname(os.path.abspath(__file__))
    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.isdir(git_dir):
        return
    try:
        # Fetch latest from remote (silent)
        subprocess.run(["git", "fetch", "--quiet"], cwd=repo_dir,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        # Check if local is behind
        local = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir,
                               capture_output=True, text=True, timeout=10).stdout.strip()
        remote = subprocess.run(["git", "rev-parse", "@{u}"], cwd=repo_dir,
                                capture_output=True, text=True, timeout=10).stdout.strip()
        if not remote or local == remote:
            return
        # Pull changes
        result = subprocess.run(["git", "pull", "--ff-only", "--quiet"], cwd=repo_dir,
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            # Check if requirements changed
            req_result = subprocess.run(["git", "diff", "--name-only", local, remote],
                                        cwd=repo_dir, capture_output=True, text=True, timeout=10)
            if "requirements.txt" in req_result.stdout:
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"],
                               cwd=repo_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)
            print(f"\033[93m[KEYZBOT] Updated! Restarting...\033[0m")
            os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception:
        pass  # Silent fail — don't block startup

_auto_update()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import config, ui, agent, memory, plan, tasks, hooks, skills, scheduler, subagents, permissions
from core.config import save_history, load_history, list_history

VERSION = "9.1"

# ─── Commands ─────────────────────────────────────────────────────────────────
def cmd_help():
    ui.cmd_box("Commands", [
        f"{ui.S.BGRN}/help{ui.S.R}          Show this help",
        f"{ui.S.BGRN}/clear{ui.S.R}         Clear conversation",
        f"{ui.S.BGRN}/model{ui.S.R}         Show/change model",
        f"{ui.S.BGRN}/temp{ui.S.R}          Show/change temperature",
        f"{ui.S.BGRN}/tokens{ui.S.R}        Show token usage",
        f"{ui.S.BGRN}/history{ui.S.R}       List past sessions",
        f"{ui.S.BGRN}/load{ui.S.R}          Load a past session",
        f"{ui.S.BGRN}/config{ui.S.R}        Show current config",
        f"{ui.S.BGRN}/system{ui.S.R}        Show/change system prompt",
        f"{ui.S.BGRN}/export{ui.S.R}        Export chat to file",
        f"{ui.S.BGRN}/reset{ui.S.R}         Reset config to defaults",
        f"{ui.S.BGRN}/cd{ui.S.R}            Change working directory",
        f"{ui.S.BGRN}/pwd{ui.S.R}           Show working directory",
        f"{ui.S.BGRN}/setdir{ui.S.R}        Set persistent default work dir",
        f"{ui.S.BGRN}/tools{ui.S.R}         List available tools",
        f"{ui.S.BGRN}/browse{ui.S.R}        Browse directory tree",
        f"{ui.S.BGRN}/fast{ui.S.R}          Toggle fast mode",
        f"{ui.S.BGRN}/compact{ui.S.R}       Compact conversation context",
        "",
        f"  {ui.S.BCYN}Memory:{ui.S.R}",
        f"{ui.S.BGRN}/remember{ui.S.R}      Save a memory",
        f"{ui.S.BGRN}/recall{ui.S.R}        Search/list memories",
        f"{ui.S.BGRN}/forget{ui.S.R}        Delete a memory",
        "",
        f"  {ui.S.BCYN}Plan & Tasks:{ui.S.R}",
        f"{ui.S.BGRN}/plan{ui.S.R}          Enter/manage plan mode",
        f"{ui.S.BGRN}/tasks{ui.S.R}         List/create/update tasks",
        "",
        f"  {ui.S.BCYN}Agents:{ui.S.R}",
        f"{ui.S.BGRN}/fork{ui.S.R}          Spawn a sub-agent",
        f"{ui.S.BGRN}/agents{ui.S.R}        List active agents",
        "",
        f"  {ui.S.BCYN}Advanced:{ui.S.R}",
        f"{ui.S.BGRN}/skills{ui.S.R}        List/run skills",
        f"{ui.S.BGRN}/hooks{ui.S.R}         Manage hooks",
        f"{ui.S.BGRN}/cron{ui.S.R}          Manage scheduled tasks",
        f"{ui.S.BGRN}/permissions{ui.S.R}   Manage tool permissions",
        f"{ui.S.BGRN}/sandbox{ui.S.R}     Sandbox mode (off/warn/block)",
        f"{ui.S.BGRN}/exit{ui.S.R}          Exit KEYZBOT",
    ])

def cmd_tools():
    tools_list = [
        f"  {ui.S.BCYN}File Operations:{ui.S.R}",
        f"{ui.S.BBLU}read_file{ui.S.R}    Read file contents (auto-detects images)",
        f"{ui.S.BBLU}write_file{ui.S.R}   Write/create files",
        f"{ui.S.BBLU}edit_file{ui.S.R}    Edit files (exact replace with line numbers)",
        f"{ui.S.BBLU}glob_files{ui.S.R}   Find files by pattern",
        f"{ui.S.BBLU}grep_files{ui.S.R}   Search file contents (regex)",
        f"{ui.S.BBLU}list_dir{ui.S.R}     List directory contents (hidden option)",
        f"{ui.S.BBLU}tree{ui.S.R}         Show directory tree",
        f"  {ui.S.BCYN}Shell & System:{ui.S.R}",
        f"{ui.S.BBLU}bash{ui.S.R}         Execute shell commands (background support)",
        f"{ui.S.BBLU}monitor_start{ui.S.R} Start background process",
        f"{ui.S.BBLU}monitor_output{ui.S.R} Get process output",
        f"{ui.S.BBLU}monitor_stop{ui.S.R}  Stop background process",
        f"  {ui.S.BCYN}Web:{ui.S.R}",
        f"{ui.S.BBLU}web_search{ui.S.R}   Search the web (SearXNG + fallback)",
        f"{ui.S.BBLU}web_fetch{ui.S.R}    Fetch URL content (with prompt extraction)",
        f"  {ui.S.BCYN}Git:{ui.S.R}",
        f"{ui.S.BBLU}git{ui.S.R}          Git operations (status/diff/log/commit/branch)",
        f"  {ui.S.BCYN}Notebooks:{ui.S.R}",
        f"{ui.S.BBLU}notebook_read{ui.S.R}  Read Jupyter notebook",
        f"{ui.S.BBLU}notebook_edit{ui.S.R}  Edit notebook cells",
        f"{ui.S.BBLU}notebook_run{ui.S.R}   Run notebook cells",
        f"  {ui.S.BCYN}Images:{ui.S.R}",
        f"{ui.S.BBLU}read_image{ui.S.R}   Read image (multimodal vision)",
        f"  {ui.S.BCYN}Agent & Memory:{ui.S.R}",
        f"{ui.S.BBLU}save_memory{ui.S.R}  Save to persistent memory",
        f"{ui.S.BBLU}load_memory{ui.S.R}  Search/load from memory",
        f"{ui.S.BBLU}read_plan{ui.S.R}    Read active plan",
        f"{ui.S.BBLU}update_plan{ui.S.R}  Update active plan",
        f"{ui.S.BBLU}spawn_agent{ui.S.R}  Spawn a sub-agent",
        f"{ui.S.BBLU}run_skill{ui.S.R}    Execute a skill",
        f"  {ui.S.BCYN}Tasks & Scheduling:{ui.S.R}",
        f"{ui.S.BBLU}task_create{ui.S.R}  Create a tracked task",
        f"{ui.S.BBLU}task_update{ui.S.R}  Update task status",
        f"{ui.S.BBLU}task_list{ui.S.R}    List all tasks",
        f"{ui.S.BBLU}cron_create{ui.S.R}  Schedule recurring task",
        f"{ui.S.BBLU}cron_list{ui.S.R}    List scheduled jobs",
        f"{ui.S.BBLU}cron_delete{ui.S.R}  Delete scheduled job",
        f"  {ui.S.BCYN}Interaction:{ui.S.R}",
        f"{ui.S.BBLU}ask_user{ui.S.R}     Ask user a question with options",
        f"  {ui.S.BCYN}MCP:{ui.S.R}",
        f"{ui.S.BBLU}mcp_list{ui.S.R}     List MCP servers",
        f"{ui.S.BBLU}mcp_call{ui.S.R}     Call MCP tool",
        f"  {ui.S.BCYN}DevTools:{ui.S.R}",
        f"{ui.S.BBLU}detect_project{ui.S.R} Auto-detect project type",
        f"{ui.S.BBLU}lint{ui.S.R}         Run linter (ESLint/Pylint/ruff)",
        f"{ui.S.BBLU}test_runner{ui.S.R}  Run tests (pytest/jest/cargo)",
        f"{ui.S.BBLU}github{ui.S.R}      GitHub PR/issue/repo ops",
        f"{ui.S.BBLU}read_document{ui.S.R} Read PDF/DOCX files",
    ]
    ui.cmd_box(f"Available Tools (33 total)", tools_list)

# ─── Command Handlers ─────────────────────────────────────────────────────────
def handle_memory_cmd(cmd, arg):
    if cmd == "/remember":
        if not arg:
            ui.cmd_box("Usage", [f"{ui.S.D}/remember <name>: <content>{ui.S.R}",
                                  f"{ui.S.D}/remember <content>  (auto-names){ui.S.R}"])
            return
        if ":" in arg:
            name, content = arg.split(":", 1)
            fpath = memory.save(name.strip(), content.strip())
        else:
            name = arg[:40]
            fpath = memory.save(name, arg)
        ui.success_box(f"Saved to {ui.S.BWHT}{fpath}{ui.S.R}")

    elif cmd == "/recall":
        if arg:
            results = memory.search(arg)
            if results:
                lines = [f"{ui.S.BYLW}{r['name']}{ui.S.R} — {r['description']}" for r in results]
                ui.cmd_box(f"Search: {arg}", lines)
            else:
                ui.cmd_box(f"Search: {arg}", [f"{ui.S.D}No memories found.{ui.S.R}"])
        else:
            mems = memory.list_memories()
            if mems:
                lines = [f"{ui.S.BYLW}{m['name']}{ui.S.R} [{m['type']}] {m['description'][:60]}" for m in mems]
                ui.cmd_box("Memories", lines)
            else:
                ui.cmd_box("Memories", [f"{ui.S.D}No memories saved. Use /remember to save.{ui.S.R}"])

    elif cmd == "/forget":
        if not arg:
            ui.cmd_box("Usage", [f"{ui.S.D}/forget <name>{ui.S.R}"])
            return
        if memory.delete(arg):
            ui.success_box(f"Deleted memory: {arg}")
        else:
            ui.error_box(f"Memory not found: {arg}")

def handle_plan_cmd(arg):
    active = plan.get_active()
    if not arg:
        if active:
            content = plan.read()
            print(f"\n  {ui.S.BCYN}Active Plan:{ui.S.R}")
            for line in content.split("\n")[:30]:
                print(f"    {line}")
            print()
        else:
            plans = plan.list_plans()
            if plans:
                lines = [f"{ui.S.BYLW}{p['title']}{ui.S.R} [{p['status']}]" for p in plans]
                ui.cmd_box("Plans", lines)
            else:
                ui.cmd_box("Plan Mode", [f"{ui.S.D}/plan <title> — create new plan{ui.S.R}",
                                          f"{ui.S.D}/plan exit — exit plan mode{ui.S.R}"])
        return

    parts = arg.split(None, 1)
    sub = parts[0].lower()

    if sub == "exit":
        if active:
            path = plan.exit_plan()
            ui.success_box(f"Plan saved: {path}")
        else:
            ui.error_box("No active plan")

    elif sub == "list":
        plans = plan.list_plans()
        if plans:
            lines = [f"{ui.S.BYLW}{p['title']}{ui.S.R} [{p['status']}]" for p in plans]
            ui.cmd_box("Plans", lines)
        else:
            ui.cmd_box("Plans", [f"{ui.S.D}No plans found.{ui.S.R}"])

    elif sub == "status":
        if active and len(parts) > 1:
            plan.mark_status(parts[1])
            ui.success_box(f"Status: {parts[1]}")
        else:
            ui.error_box("No active plan or missing status")

    else:
        # Create new plan with the full arg as title
        path = plan.enter(arg)
        ui.success_box(f"Plan mode entered: {path}")
        print(f"  {ui.S.D}Use /plan exit to save and exit plan mode{ui.S.R}\n")

def handle_tasks_cmd(arg):
    if not arg:
        all_tasks = tasks.list_all()
        if all_tasks:
            lines = []
            for t in all_tasks:
                icon = {"pending": "○", "in_progress": "◉", "completed": "●"}.get(t["status"], "?")
                color = {"pending": ui.S.D, "in_progress": ui.S.BYLW, "completed": ui.S.BGRN}.get(t["status"], "")
                lines.append(f"{color}{icon} [{t['id']}] {t['subject']}{ui.S.R}")
            ui.cmd_box("Tasks", lines)
        else:
            ui.cmd_box("Tasks", [f"{ui.S.D}No tasks. /tasks create <subject>{ui.S.R}"])
        return

    parts = arg.split(None, 2)
    sub = parts[0].lower()

    if sub == "create" and len(parts) > 1:
        subj = parts[1] + (" " + parts[2] if len(parts) > 2 else "")
        t = tasks.create(subj)
        ui.success_box(f"Task #{t['id']}: {subj}")

    elif sub == "done" and len(parts) > 1:
        t = tasks.update(parts[1], status="completed")
        if t:
            ui.success_box(f"Task #{t['id']} completed")
        else:
            ui.error_box(f"Task not found: {parts[1]}")

    elif sub == "start" and len(parts) > 1:
        t = tasks.update(parts[1], status="in_progress")
        if t:
            ui.success_box(f"Task #{t['id']} started")
        else:
            ui.error_box(f"Task not found: {parts[1]}")

    elif sub == "delete" and len(parts) > 1:
        tasks.delete(parts[1])
        ui.success_box(f"Task #{parts[1]} deleted")

    elif sub == "get" and len(parts) > 1:
        t = tasks.get(parts[1])
        if t:
            ui.cmd_box(f"Task #{t['id']}", [
                f"Subject: {t['subject']}", f"Status:  {t['status']}",
                f"Owner:   {t.get('owner','')}", f"Created: {t.get('created','')}",
                f"Blocks:  {', '.join(t.get('blocks',[])) or 'none'}",
                f"Blocked: {', '.join(t.get('blockedBy',[])) or 'none'}",
            ])
        else:
            ui.error_box(f"Task not found: {parts[1]}")

def handle_fork_cmd(arg, bot=None):
    if not arg:
        types = subagents.get_types()
        lines = [f"{ui.S.BBLU}{k}{ui.S.R} — {v['description'][:60]}" for k, v in types.items()]
        ui.cmd_box("Agent Types", lines + ["", f"{ui.S.D}/fork <name> <type> <task>{ui.S.R}",
                                             f"{ui.S.D}/fork <type> <task>  (auto-named){ui.S.R}"])
        return

    parts = arg.split(None, 2)
    types = subagents.get_types()

    if len(parts) < 2:
        ui.error_box("Usage: /fork <name> <type> <task> or /fork <type> <task>")
        return

    if parts[1] in types:
        name = parts[0]
        atype = parts[1]
        task = parts[2] if len(parts) > 2 else ""
    elif parts[0] in types:
        name = f"agent-{int(time.time()) % 10000}"
        atype = parts[0]
        task = parts[1] + (" " + parts[2] if len(parts) > 2 else "")
    else:
        ui.error_box(f"Unknown type: {parts[0]}. Available: {', '.join(types.keys())}")
        return

    if not task:
        ui.error_box("No task provided")
        return

    ui.spinner_box(f"Spawning {atype} agent: {name}")
    wd = bot.work_dir if bot else None
    result = subagents.spawn(name, task, atype, bot, work_dir=wd, background=True)
    ui.success_box(f"Agent '{name}' ({atype}) started in background")

def handle_skills_cmd(arg):
    if not arg:
        all_skills = skills.list_skills()
        lines = [f"{ui.S.BBLU}{k}{ui.S.R} — {v.get('description','')[:50]}" for k, v in all_skills.items()]
        ui.cmd_box("Skills", lines + ["", f"{ui.S.D}/skills <name> — run a skill{ui.S.R}"])
        return

    sk = skills.get_skill(arg)
    if sk:
        prompt = sk.get("prompt", "")
        if prompt.startswith("LOOP:"):
            ui.cmd_box("Loop Skill", [f"{ui.S.D}Usage: /loop <interval_seconds> <prompt>{ui.S.R}"])
            return
        # Run the skill as a user message
        return prompt
    else:
        ui.error_box(f"Skill not found: {arg}")
        return None

def handle_hooks_cmd(arg):
    if not arg:
        h = hooks.load_hooks()
        if h:
            lines = []
            for event, hook_list in h.items():
                for h_item in hook_list:
                    lines.append(f"{ui.S.BYLW}{event}{ui.S.R}: {h_item.get('command','')[:60]}")
            ui.cmd_box("Hooks", lines)
        else:
            ui.cmd_box("Hooks", [f"{ui.S.D}No hooks configured.{ui.S.R}",
                                  f"{ui.S.D}/hooks add <event> <command>{ui.S.R}",
                                  f"{ui.S.D}Events: pre_tool_call, post_tool_call{ui.S.R}"])
        return

    parts = arg.split(None, 2)
    sub = parts[0].lower()

    if sub == "add" and len(parts) > 2:
        hooks.add_hook(parts[1], parts[2])
        ui.success_box(f"Hook added for {parts[1]}")
    elif sub == "clear":
        event = parts[1] if len(parts) > 1 else None
        hooks.remove_hooks(event)
        ui.success_box("Hooks cleared")
    else:
        ui.error_box("Usage: /hooks add <event> <command> | /hooks clear [event]")

def handle_cron_cmd(arg):
    if not arg:
        jobs = scheduler.list_jobs()
        if jobs:
            lines = []
            for j in jobs:
                status = "active" if j.get("active") else "inactive"
                lines.append(f"[{ui.S.BYLW}{j['id']}{ui.S.R}] {j['cron']} — {j['prompt'][:50]} ({status})")
            ui.cmd_box("Scheduled Jobs", lines)
        else:
            ui.cmd_box("Scheduler", [f"{ui.S.D}No scheduled jobs.{ui.S.R}",
                                      f"{ui.S.D}/cron add <cron_expr> <prompt>{ui.S.R}",
                                      f"{ui.S.D}/cron del <id>{ui.S.R}"])
        return

    parts = arg.split(None, 2)
    sub = parts[0].lower()

    if sub == "add" and len(parts) > 2:
        job = scheduler.create(parts[1], parts[2])
        ui.success_box(f"Job #{job['id']}: {parts[1]} → {parts[2][:40]}")
    elif sub == "del" and len(parts) > 1:
        scheduler.delete(parts[1])
        ui.success_box(f"Job #{parts[1]} deleted")
    elif sub == "list":
        jobs = scheduler.list_jobs()
        for j in jobs:
            print(f"  [{j['id']}] {j['cron']} — {j['prompt']}")
    else:
        ui.error_box("Usage: /cron add <cron> <prompt> | /cron del <id>")

def handle_permissions_cmd(arg):
    if not arg:
        mode = permissions.get_mode()
        modes = permissions.get_modes()
        lines = [f"{ui.S.BGRN}Current mode: {mode}{ui.S.R}", ""]
        for k, v in modes.items():
            marker = " ◀" if k == mode else ""
            lines.append(f"  {ui.S.BYLW}{k}{ui.S.R} — {v}{marker}")
        ui.cmd_box("Permissions", lines + ["", f"{ui.S.D}/permissions <mode>  (auto|confirm|smart){ui.S.R}"])
        return

    if permissions.set_mode(arg):
        ui.success_box(f"Permission mode: {arg}")
    else:
        ui.error_box(f"Unknown mode: {arg}. Use: auto, confirm, smart")

def handle_sandbox_cmd(arg):
    if not arg:
        mode = permissions.get_sandbox_mode()
        modes_info = {"off": "No sandbox (all commands allowed)", "warn": "Warn on dangerous commands", "block": "Block dangerous commands"}
        lines = [f"{ui.S.BGRN}Current sandbox: {mode}{ui.S.R}", ""]
        for k, v in modes_info.items():
            marker = " ◀" if k == mode else ""
            lines.append(f"  {ui.S.BYLW}{k}{ui.S.R} — {v}{marker}")
        ui.cmd_box("Sandbox", lines + ["", f"{ui.S.D}/sandbox <mode>  (off|warn|block){ui.S.R}"])
        return
    if permissions.set_sandbox_mode(arg):
        ui.success_box(f"Sandbox mode: {arg}")
    else:
        ui.error_box(f"Unknown mode: {arg}. Use: off, warn, block")

def handle_agents_cmd(arg):
    active = subagents.list_active()
    if active:
        lines = []
        for name, info in active.items():
            lines.append(f"{ui.S.BYLW}{name}{ui.S.R} [{info['type']}] — {info['status']} — {info['task']}")
        ui.cmd_box("Active Agents", lines)
    else:
        ui.cmd_box("Agents", [f"{ui.S.D}No active agents. Use /fork to spawn.{ui.S.R}"])

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    cfg = config.get_or_create()
    if not cfg:
        cfg = ui.setup()

    bot = agent.Agent(cfg)
    # Smart work dir: use config default, not KEYZBOT's own directory
    default_wd = cfg.get("default_work_dir", "/sdcard/Documents")
    bot.work_dir = default_wd if os.path.isdir(default_wd) else os.getcwd()

    # Init memory
    memory.init()

    ui.banner(cfg)

    # Show quick start hints
    tool_count = len(bot.tools)
    print(f"  {ui.S.D}Work Dir: {bot.work_dir} | Tools: {tool_count} | Type /help for commands{ui.S.R}")
    print(f"  {ui.S.D}Quick: /browse [path] · /compact · /setdir <path> · /fast{ui.S.R}\n")

    sid = time.strftime("%Y%m%d_%H%M%S")

    try:
        while True:
            ui.show_cur()
            plan_active = plan.get_active()
            prompt_icon = f" {ui.S.BMAG}▶{ui.S.R} " if plan_active else f" "
            sys.stdout.write(f"  {ui.S.BGRN}{ui.S.B}You{ui.S.R}{prompt_icon}")
            sys.stdout.flush()

            try:
                user = input().strip()
            except (KeyboardInterrupt, EOFError):
                save_history(sid, bot.messages)
                print(f"\n\n  {ui.S.D}Goodbye!{ui.S.R}\n")
                break

            if not user:
                continue

            # ── Commands ──
            if user.startswith("/"):
                parts = user.split(None, 1)
                cmd = parts[0].lower()
                arg = parts[1] if len(parts) > 1 else ""

                if cmd in ("/exit", "/quit"):
                    save_history(sid, bot.messages)
                    print(f"\n  {ui.S.D}Goodbye!{ui.S.R}\n")
                    break

                elif cmd == "/help":
                    cmd_help()
                elif cmd == "/tools":
                    cmd_tools()
                elif cmd == "/clear":
                    bot.clear()
                    sid = time.strftime("%Y%m%d_%H%M%S")
                    ui.banner(cfg)

                elif cmd == "/model":
                    if arg:
                        cfg["model"] = arg
                        config.save(cfg)
                        bot.cfg = cfg
                        ui.success_box(f"Model: {ui.S.BWHT}{arg}{ui.S.R}")
                    else:
                        ui.cmd_box("Model", [f"{ui.S.BWHT}{cfg['model']}{ui.S.R}", "",
                                              f"{ui.S.D}/model <name>{ui.S.R}"])

                elif cmd == "/temp":
                    if arg:
                        try:
                            t = float(arg)
                            cfg["temperature"] = max(0, min(2, t))
                            config.save(cfg)
                            bot.cfg = cfg
                            ui.success_box(f"Temp: {ui.S.BWHT}{cfg['temperature']}{ui.S.R}")
                        except ValueError:
                            ui.error_box("Invalid number")
                    else:
                        ui.cmd_box("Temperature", [f"{ui.S.BWHT}{cfg['temperature']}{ui.S.R}", "",
                                                    f"{ui.S.D}/temp <0.0-2.0>{ui.S.R}"])

                elif cmd == "/tokens":
                    ui.cmd_box("Tokens", [
                        f"Session: {ui.S.BWHT}{bot.tokens}{ui.S.R}",
                        f"Input:   {ui.S.BWHT}{bot.input_tokens}{ui.S.R}",
                        f"Output:  {ui.S.BWHT}{bot.output_tokens}{ui.S.R}",
                        f"Cost:    {ui.S.BGRN}{bot.get_cost_summary()}{ui.S.R}",
                        f"Max:     {ui.S.BWHT}{cfg['max_tokens']}{ui.S.R}",
                    ])

                elif cmd == "/history":
                    files = list_history()
                    if files:
                        ls = [f"{ui.S.BYLW}{i}{ui.S.R}. {f.stem}" for i, f in enumerate(files[:10], 1)]
                        ui.cmd_box("History", ls)
                    else:
                        ui.cmd_box("History", [f"{ui.S.D}No sessions found.{ui.S.R}"])

                elif cmd == "/load":
                    if arg:
                        h = load_history(arg)
                        if h:
                            bot.messages = h
                            bot.tokens = sum(len(m.get("content", "") or "") for m in h) // 4
                            ui.banner(cfg)
                            print(f"  {ui.S.BGRN}Loaded: {arg}{ui.S.R}\n")
                        else:
                            ui.error_box("Session not found")
                    else:
                        ui.cmd_box("Usage", [f"{ui.S.D}/load <session-id>{ui.S.R}"])

                elif cmd == "/config":
                    m = cfg['api_key'][:12] + "..." + cfg['api_key'][-4:] if len(cfg['api_key']) > 16 else "***"
                    ui.cmd_box("Config", [
                        f"{ui.S.D}URL      {ui.S.R}  {cfg['base_url']}",
                        f"{ui.S.D}Model    {ui.S.R}  {cfg['model']}",
                        f"{ui.S.D}Temp     {ui.S.R}  {cfg['temperature']}",
                        f"{ui.S.D}Tokens   {ui.S.R}  {cfg['max_tokens']}",
                        f"{ui.S.D}Key      {ui.S.R}  {m}",
                        f"{ui.S.D}Work Dir {ui.S.R}  {bot.work_dir}",
                        f"{ui.S.D}Perm     {ui.S.R}  {permissions.get_mode()}",
                    ])

                elif cmd == "/system":
                    if arg:
                        cfg["system_prompt"] = arg
                        config.save(cfg)
                        bot.cfg = cfg
                        bot.set_system_prompt(arg)
                        ui.success_box("System prompt updated")
                    else:
                        ui.cmd_box("System Prompt", [cfg['system_prompt'], "",
                                                     f"{ui.S.D}/system <prompt>{ui.S.R}"])

                elif cmd == "/export":
                    fpath = config.DIR / f"chat_{sid}.txt"
                    with open(fpath, "w") as f:
                        for m in bot.messages:
                            if m["role"] == "system":
                                continue
                            if m["role"] == "tool":
                                f.write(f"[TOOL: {m.get('tool_call_id','')}]\n{m['content']}\n\n")
                                continue
                            tc = m.get("tool_calls")
                            if tc:
                                for t in tc:
                                    f.write(f"[TOOL CALL: {t['function']['name']}]\n{t['function']['arguments']}\n\n")
                                continue
                            content = m.get("content", "")
                            if content:
                                f.write(f"[{m['role'].upper()}]\n{content}\n\n")
                    ui.success_box(f"Exported: {ui.S.BWHT}{fpath}{ui.S.R}")

                elif cmd == "/cd":
                    if arg:
                        path = os.path.expanduser(arg)
                        if os.path.isdir(path):
                            os.chdir(path)
                            bot.work_dir = os.getcwd()
                            ui.success_box(f"Dir: {bot.work_dir}")
                        else:
                            ui.error_box(f"Not a directory: {arg}")
                    else:
                        ui.cmd_box("Work Dir", [bot.work_dir])

                elif cmd == "/pwd":
                    ui.cmd_box("Work Dir", [bot.work_dir])

                elif cmd == "/browse":
                    from tools import file_ops
                    path = arg or bot.work_dir or "/sdcard/Documents"
                    path = os.path.expanduser(path)
                    result = file_ops.execute("tree", {"path": path, "depth": 3})
                    print(result)

                elif cmd == "/setdir":
                    if arg:
                        path = os.path.expanduser(arg)
                        if os.path.isdir(path):
                            cfg["default_work_dir"] = path
                            config.save(cfg)
                            bot.work_dir = path
                            bot.set_system_prompt(cfg["system_prompt"])
                            ui.success_box(f"Default dir: {path}")
                        else:
                            ui.error_box(f"Not a directory: {arg}")
                    else:
                        current = cfg.get("default_work_dir", "/sdcard/Documents")
                        ui.cmd_box("Default Work Dir", [f"Current: {current}", "",
                                                        f"{ui.S.D}/setdir <path> to change{ui.S.R}"])

                elif cmd == "/reset":
                    if arg == "confirm":
                        cfg = config.auto_detect()
                        config.save(cfg)
                        bot = agent.Agent(cfg)
                        bot.work_dir = os.getcwd()
                        ui.banner(cfg)
                        print(f"  {ui.S.BYLW}Reset done.{ui.S.R}\n")
                    else:
                        ui.cmd_box("Reset", [f"{ui.S.BYLW}/reset confirm{ui.S.R}"])

                elif cmd == "/fast":
                    if not hasattr(bot, '_fast_mode'):
                        bot._fast_mode = False
                    bot._fast_mode = not bot._fast_mode
                    if bot._fast_mode:
                        bot._orig_temp = bot.cfg.get("temperature", 0.7)
                        bot.cfg["temperature"] = 0.3
                        ui.success_box("Fast mode ON — lower temperature for faster, more focused output")
                    else:
                        bot.cfg["temperature"] = bot._orig_temp
                        ui.success_box("Fast mode OFF — normal temperature restored")

                elif cmd == "/compact":
                    if len(bot.messages) > 4:
                        sys_msg = bot.messages[0]
                        last_msgs = bot.messages[-4:]
                        removed_msgs = bot.messages[1:-4]  # Exclude system and last 4
                        removed = len(removed_msgs)
                        # Generate summary of dropped messages
                        summary_parts = []
                        for m in removed_msgs:
                            role = m.get("role", "unknown")
                            content = m.get("content", "")
                            if isinstance(content, str) and content:
                                preview = content[:100] + ("..." if len(content) > 100 else "")
                                summary_parts.append(f"[{role}]: {preview}")
                        if summary_parts:
                            summary = "[Conversation Summary]\n" + "\n".join(summary_parts[-10:])  # Keep last 10 previews
                            bot.messages = [sys_msg, {"role": "system", "content": summary}] + last_msgs
                        else:
                            bot.messages = [sys_msg] + last_msgs
                        ui.success_box(f"Compacted: removed {removed} messages")
                    else:
                        ui.success_box("Already compact")

                # Memory commands
                elif cmd in ("/remember", "/recall", "/forget"):
                    handle_memory_cmd(cmd, arg)

                # Plan mode
                elif cmd == "/plan":
                    handle_plan_cmd(arg)

                # Tasks
                elif cmd == "/tasks":
                    handle_tasks_cmd(arg)

                # Fork / sub-agents
                elif cmd == "/fork":
                    handle_fork_cmd(arg, bot)

                elif cmd == "/agents":
                    handle_agents_cmd(arg)

                # Skills
                elif cmd == "/skills":
                    result = handle_skills_cmd(arg)
                    if result and isinstance(result, str):
                        # Skill returned a prompt — run it as chat
                        bot.chat(result)
                        ui.status_line(bot.tokens, cfg["model"])

                # Hooks
                elif cmd == "/hooks":
                    handle_hooks_cmd(arg)

                # Scheduler
                elif cmd == "/cron":
                    handle_cron_cmd(arg)

                # Permissions
                elif cmd == "/permissions":
                    handle_permissions_cmd(arg)

                elif cmd == "/sandbox":
                    handle_sandbox_cmd(arg)

                else:
                    ui.cmd_box("Error", [
                        f"{ui.S.BRED}Unknown: {cmd}{ui.S.R}",
                        f"{ui.S.D}/help for commands{ui.S.R}",
                    ])
                continue

            # ── If in plan mode, offer to save to plan ──
            if plan_active:
                plan_content = plan.read()
                plan.update(plan_content + f"\n\n**User input:** {user}")

            # ── Chat with agent ──
            response = bot.chat(user)
            ui.status_line(bot.tokens, cfg["model"])

    finally:
        ui.show_cur()


if __name__ == "__main__":
    # Default: web mode. Use --cli for terminal mode.
    if "--cli" in sys.argv:
        main()
    else:
        port = 8080
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    pass
        from web.server import start_web
        start_web(port=port)
