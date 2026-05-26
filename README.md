<div align="center">

# KEYZBOT

**Autonomous AI Agent for Android & Linux**

<br>

![Version](https://img.shields.io/badge/version-9.2-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.8+-green?style=for-the-badge)
![Tools](https://img.shields.io/badge/tools-36-orange?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-95%20passed-brightgreen?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-purple?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-Termux%20%7C%20Linux-lightgrey?style=for-the-badge)

<br>

![Stars](https://img.shields.io/github/stars/muzaqidev/KEYZBOT?style=for-the-badge)
![Forks](https://img.shields.io/github/forks/muzaqidev/KEYZBOT?style=for-the-badge)
![Issues](https://img.shields.io/github/issues/muzaqidev/KEYZBOT?style=for-the-badge)
![Last Commit](https://img.shields.io/github/last-commit/muzaqidev/KEYZBOT?style=for-the-badge)

<br>

Full-stack autonomous coding agent that runs natively on Android via Termux.

**36 built-in tools. Web UI. Multi-provider. No API key needed to start.**

<br>

**[Quick Start](#quick-start)** &nbsp;&middot;&nbsp;
**[Features](#features)** &nbsp;&middot;&nbsp;
**[Providers](#provider-management)** &nbsp;&middot;&nbsp;
**[Tools](#tools)** &nbsp;&middot;&nbsp;
**[Contributors](#contributors)**

</div>

---

## Features

| Feature | Description |
|---------|-------------|
| **Zero Config** | OpenGateway pre-configured. Clone, install, run. No API key needed to start. |
| **36 Built-in Tools** | Bash, file ops, git, web search, image analysis, scheduling, GitHub API, and more. |
| **Multi-Provider** | Switch between OpenGateway, Groq, SambaNova, Cerebras, OpenRouter, or any OpenAI-compatible API. |
| **Web UI** | Dark/light theme, streaming responses, chat history, tool panels, drag-and-drop file upload. |
| **Multi-Chat** | Create, switch, rename, delete conversations. Full session persistence across refreshes. |
| **Multimodal Vision** | Upload images alongside text. AI analyzes them in real-time. Auto-compressed. |
| **Sub-Agents** | Fork background agents for parallel task execution. |
| **Plan & Tasks** | Structured planning mode with task tracking and dependency management. |
| **Persistent Memory** | Remember, recall, and forget across sessions. |
| **Auto-Update** | Checks GitHub every 5 minutes. One-click update from Web UI or auto-pull in CLI. |
| **Streaming Resilience** | Server continues processing even if client disconnects mid-stream. |
| **CLI + Web** | Terminal or browser. Same engine, two interfaces. |

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-SocketIO-000000?style=for-the-badge&logo=flask&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/CI/CD-GitHub%20Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)

---

## Quick Start

### 1. Install Termux (Android)

Download from **F-Droid** (not Play Store):

```
https://f-droid.org/packages/com.termux/
```

### 2. Setup Environment

```bash
pkg update && pkg upgrade -y
pkg install python git -y
```

### 3. Clone & Run

```bash
git clone https://github.com/muzaqidev/KEYZBOT.git
cd KEYZBOT
pip install -r requirements.txt
bash install.sh
```

### 4. Launch

```bash
# CLI mode
keyzbot

# Web UI mode
python3 web/server.py
# Open http://localhost:8080
```

OpenGateway is pre-configured. Just start chatting.

---

## Provider Management

KEYZBOT supports any OpenAI-compatible API. Manage providers from the web UI or `providers.json`.

### Built-in Presets

| Provider | Model | Free Tier |
|----------|-------|-----------|
| **OpenGateway** | mimo-v2.5-pro | Yes |
| **Groq** | Llama 3.3 70B | Yes |
| **SambaNova** | DeepSeek V3.1 | Yes |
| **Cerebras** | Llama 3.1 8B | Yes |
| **OpenRouter** | 100+ models | Pay-per-use |

### Custom Provider

Add via **Web UI** (Settings > Providers > Add) or edit `providers.json`:

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

```bash
keyzbot                       # interactive mode
keyzbot "explain this code"   # one-shot query
keyzbot /tools                # list all tools
keyzbot /model sambanova      # switch provider
keyzbot /fork "refactor src"  # spawn sub-agent
```

### Web UI Commands

| Command | Action |
|---------|--------|
| `/model` | Switch model or provider |
| `/tools` | List available tools |
| `/clear` | Clear current chat |
| `/export` | Export chat (json/text/markdown) |
| `/fast` | Toggle fast output mode |
| `/help` | Show all commands |

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

36 built-in tools across 16 modules.

| Category | Tools | Description |
|----------|-------|-------------|
| **Shell** | `bash` | Execute shell commands with timeout and working directory control |
| **Files** | `read_file` `write_file` `edit_file` `glob_files` `grep_files` `list_dir` `tree` | Full filesystem operations — read, write, edit, search, list, tree view |
| **Git** | `git` | Full git CLI — commit, push, pull, diff, log, branch, etc. |
| **GitHub** | `github` | GitHub API — PRs, issues, releases, checks, comments |
| **Web** | `web_search` `web_fetch` `read_document` | Web search via SearXNG, page extraction via Jina, document parsing |
| **Media** | `read_image` | Image reading and visual analysis with multimodal AI |
| **Code** | `lint` `test_runner` `notebook_read` `notebook_edit` `notebook_run` | Linting, test execution, Jupyter notebook support |
| **Monitoring** | `monitor_start` `monitor_status` `monitor_output` `monitor_stop` | Background process monitoring with stream output |
| **Project** | `detect_project` | Auto-detect project type, framework, and structure |
| **Tasks** | `task_create` `task_list` `task_update` `task_delete` | Structured task tracking with dependencies |
| **Scheduling** | `cron_create` `cron_list` `cron_delete` | Cron-based job scheduling |
| **Interaction** | `ask_user` | Interactive prompts for user input during tool execution |
| **MCP** | `mcp_list` `mcp_call` | Model Context Protocol — connect to external tool servers |

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
├── tools/                  # 36 built-in tools (16 modules)
│   ├── bash.py             # Shell execution
│   ├── file_ops.py         # File operations (read, write, edit, glob, grep, list, tree)
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
│   ├── tokenizer.py        # Token counting (utility)
│   └── mcp.py              # MCP protocol
│
└── web/                    # Web UI
    ├── server.py           # Flask + SocketIO backend
    └── static/
        ├── index.html      # UI page
        ├── app.js          # Client logic
        ├── style.css       # Theme styles (dark/light)
        └── keyzbot.svg     # Logo
```

---

## Requirements

- **Python** 3.8+
- **Termux** (Android) or any Linux/macOS terminal
- **Internet** connection (for AI API calls)
- **No API key** needed to start (OpenGateway is pre-configured)

---

## Contributing

Contributions are welcome. Here's how:

1. **Fork** this repository
2. **Create** a feature branch (`git checkout -b feature/my-feature`)
3. **Commit** your changes (`git commit -m "Add my feature"`)
4. **Push** to the branch (`git push origin feature/my-feature`)
5. **Open** a Pull Request

### What to contribute

- New tools or provider integrations
- Bug fixes and performance improvements
- Documentation and translations
- UI/UX improvements
- Test coverage

---

## Contributors

<a href="https://github.com/muzaqidev/KEYZBOT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=muzaqidev/KEYZBOT" />
</a>

---

## Star History

<a href="https://star-history.com/#muzaqidev/KEYZBOT&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=muzaqidev/KEYZBOT&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=muzaqidev/KEYZBOT&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=muzaqidev/KEYZBOT&type=Date" />
 </picture>
</a>

---

## License

MIT License

---

<div align="center">

**Built by muzaqi dev**

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/muzaqidev)

</div>
