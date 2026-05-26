<div align="center">

# KEYZBOT

**Full-Stack Autonomous AI Agent**

<br>

![Version](https://img.shields.io/badge/version-9.2-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![Tools](https://img.shields.io/badge/tools-34-orange)
![License](https://img.shields.io/badge/license-MIT-purple)
![Platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-lightgrey)

<br>

An autonomous AI coding agent with **34 built-in tools**, **multimodal vision**, **web UI**, **provider management**, and **auto-updates** — built to run natively on Android via Termux.

**Works out of the box** — no API key required to start. OpenGateway is configured by default.

</div>

---

## Highlights

| | Feature | Description |
|---|---|---|
| | **Zero Config** | OpenGateway works instantly — no API key needed. Just clone and run. |
| | **Provider Manager** | Add, edit, delete, and switch between providers from the web UI. Preset templates for Groq, SambaNova, Cerebras, OpenRouter. |
| | **Auto-Update** | Checks GitHub on every startup + every 5 minutes. Web UI shows toast notification with "Update Now" button. CLI auto-pulls and restarts. |
| | **Multimodal Chat** | Upload images alongside text. AI sees and analyzes them in real-time. Auto-compressed to 1024px JPEG 70%. |
| | **34 Tools** | Bash, file ops, git, web search, image analysis, scheduling, GitHub integration, and more. |
| | **Web UI** | Responsive interface with dark/light theme, streaming, chat history, tool panels, drag-and-drop. |
| | **Multi-Chat** | Create, switch, rename, and delete conversations. Full session persistence across refreshes. |
| | **Sub-Agents** | Fork background agents for parallel task execution. |
| | **Plan & Tasks** | Structured planning mode with task tracking and dependency management. |
| | **Memory System** | Persistent memory across sessions — remember, recall, and forget. |
| | **Streaming Resilience** | Server continues processing even if the client disconnects mid-stream. |
| | **CLI + Web** | Use from terminal or browser. Same engine, two interfaces. |

---

## Quick Start

### Step 1 — Install Termux (Android)

Download from **F-Droid** (not Play Store):

```
https://f-droid.org/packages/com.termux/
```

### Step 2 — Prepare Environment

```bash
pkg update && pkg upgrade -y
pkg install python git -y
```

### Step 3 — Clone & Install

```bash
git clone https://github.com/mygeminim-source/KEYZBOT.git
cd KEYZBOT
pip install -r requirements.txt
bash install.sh
```

### Step 4 — Launch

```bash
# CLI mode
keyzbot

# Web UI mode
python3 web/server.py
# Open http://localhost:8080
```

That's it. OpenGateway is pre-configured — no API key needed to start chatting.

---

## Provider Management

KEYZBOT supports any OpenAI-compatible API. Manage providers from the web UI or config files.

### Preset Providers (ready to use)

| Provider | Model | Free Tier | Status |
|----------|-------|-----------|--------|
| **OpenGateway** | mimo-v2.5-pro | Yes | Default |
| **Groq** | Llama 3.3 70B | Yes | Preset |
| **SambaNova** | DeepSeek V3.1 | Yes | Preset |
| **Cerebras** | Llama 3.1 8B | Yes | Preset |
| **OpenRouter** | 100+ models | Pay-per-use | Preset |
| **OpenAI** | GPT-4o | Pay-per-use | Custom |
| **Anthropic** | Claude 3.5 Sonnet | Pay-per-use | Custom |

### Custom Providers

Add custom providers via:

1. **Web UI** — Settings > Providers > Add Custom Provider
2. **Config file** — Edit `providers.json`:

```json
{
  "providers": {
    "my-provider": {
      "name": "My Provider",
      "base_url": "https://api.example.com/v1",
      "api_key": "sk-xxx",
      "model": "my-model",
      "models": ["my-model", "my-other-model"],
      "color": "#ff6b6b"
    }
  },
  "active": "my-provider"
}
```

---

## Usage

### CLI

```
keyzbot                       # interactive mode
keyzbot "explain this code"   # one-shot query
keyzbot /tools                # list all tools
keyzbot /model sambanova      # switch provider
keyzbot /fork "refactor src"  # spawn sub-agent
```

### Web UI Commands

```
/model        switch model or provider
/tools        list available tools
/clear        clear current chat
/export       export chat (json/text/markdown)
/fast         toggle fast output mode
/help         show all commands
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line |
| `Ctrl+L` | Clear chat |
| `Ctrl+K` | Toggle sidebar |
| `Ctrl+M` | Switch model |
| `/` | Focus input |

---

## Tools

| Category | Tools | Description |
|----------|-------|-------------|
| **System** | `bash` `file_ops` `monitor` | Shell execution, file read/write/edit, process monitoring |
| **Code** | `git_ops` `github` `lint_test` `notebook` | Git commands, GitHub API, linting, Jupyter notebooks |
| **Web** | `web` `doc_reader` | Web search & page extraction, document reading |
| **Media** | `image` | Image reading and visual analysis |
| **Project** | `project_detect` `tokenizer` | Auto-detect project type, token counting |
| **Productivity** | `task_tools` `cron_tools` `ask_user` | Task management, scheduled jobs, interactive prompts |
| **Extensions** | `mcp` `plugins` | Model Context Protocol, custom plugin system |

---

## Architecture

```
KEYZBOT/
├── keyzbot.py              # CLI entry point + auto-updater
├── config.json             # Active provider config
├── providers.json          # Multi-provider config
├── install.sh              # Termux installer
├── requirements.txt        # Python dependencies
│
├── core/                   # Engine
│   ├── agent.py            # AI agent loop (streaming + tool dispatch)
│   ├── config.py           # Config, providers, history management
│   ├── tools.py            # Tool router
│   ├── web_sessions.py     # Session persistence
│   ├── memory.py           # Persistent memory system
│   ├── plan.py             # Planning mode
│   ├── tasks.py            # Task tracking
│   ├── hooks.py            # Event hooks
│   ├── skills.py           # Skill system
│   ├── scheduler.py        # Cron scheduler
│   ├── subagents.py        # Background agent management
│   ├── permissions.py      # Tool permission control
│   ├── sandbox.py          # Execution sandbox
│   ├── rate_limit.py       # Rate limiting
│   ├── plugins.py          # Plugin loader
│   └── ui.py               # Terminal UI helpers
│
├── tools/                  # 34 built-in tools (16 modules)
│   ├── bash.py             # Shell execution
│   ├── file_ops.py         # File operations
│   ├── git_ops.py          # Git commands
│   ├── github.py           # GitHub API
│   ├── web.py              # Web search & fetch
│   ├── image.py            # Image analysis
│   ├── doc_reader.py       # Document parsing
│   ├── lint_test.py        # Linting & testing
│   ├── notebook.py         # Jupyter support
│   ├── task_tools.py       # Task management
│   ├── cron_tools.py       # Scheduled jobs
│   ├── ask_user.py         # Interactive prompts
│   ├── monitor.py          # Process monitoring
│   ├── project_detect.py   # Project detection
│   ├── tokenizer.py        # Token counting
│   └── mcp.py              # MCP protocol
│
├── svg/                    # Brand assets
│   └── keyzbot.svg         # Logo (1024x1024)
│
└── web/                    # Web UI
    ├── server.py           # Flask + SocketIO backend
    └── static/
        ├── index.html      # UI page
        ├── app.js          # Client logic
        ├── style.css       # Theme styles (dark/light)
        └── keyzbot.svg     # Logo for web UI
```

---

## Requirements

- **Python** 3.8+
- **Termux** (Android) or any Linux/macOS terminal
- **Internet** connection (for AI API calls)
- **No API key** needed to start (OpenGateway is pre-configured)

---

## Auto-Update

KEYZBOT checks for updates on every launch and periodically:

```
[KEYZBOT] Checking for updates...
[KEYZBOT] Updated! Restarting...
```

- Runs `git fetch` behind the scenes (30s timeout)
- Pulls only fast-forward changes (never overwrites local modifications)
- Auto-installs new dependencies if `requirements.txt` changed
- Silent fallback if offline — never blocks startup
- Web UI shows toast notification with one-click "Update Now"

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with care by WAHYU FAOSZAN MUZAQI**

2024 — 2026

</div>
