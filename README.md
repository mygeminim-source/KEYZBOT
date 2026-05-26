<div align="center">

# KEYZBOT

**Autonomous AI Agent for Android & Linux**

<br>

![Version](https://img.shields.io/badge/version-9.3-blue?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.8+-green?style=for-the-badge)
![Tools](https://img.shields.io/badge/tools-265-orange?style=for-the-badge)
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

**265 built-in tools. Web UI. Multi-provider. No API key needed to start.**

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
| **265 Built-in Tools** | Bash, file ops, git, web search, image analysis, scheduling, GitHub API, and more. |
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

265 built-in tools across 30 modules.

| Category | Tools | Count |
|----------|-------|-------|
| **Shell** | `bash` | 1 |
| **Files** | `read_file` `write_file` `edit_file` `glob_files` `grep_files` `list_dir` `tree` | 7 |
| **Git** | `git` + `git_blame` `git_search` `git_diff_stat` `git_stash_*` `git_cherry_pick` `git_rebase` `git_tag` `git_contributors` `git_file_history` `git_restore` `git_clean` `git_hooks_list` | 14 |
| **GitHub** | `github` (PRs, issues, repos, gists, API) | 1 |
| **Web** | `web_search` `web_fetch` `read_document` | 3 |
| **Network** | `http_request` `api_test` `dns_lookup` `port_check` `port_scan` `whois_lookup` `ssl_check` `ping_host` `url_parse` `curl_parse` `network_interfaces` `traceroute` `download_file` `upload_file` `webhook_send` `local_ip` | 16 |
| **Media** | `read_image` `image_resize` `image_convert` `image_crop` `image_info` `image_compress` `video_info` `video_to_gif` `video_thumbnail` `audio_info` `audio_convert` `audio_extract` `qr_generate` `qr_read` `screenshot` | 15 |
| **Data** | `db_connect` `db_query` `db_schema` `db_dump` `csv_read` `csv_write` `json_read` `json_write` `json_query` `json_merge` `json_to_csv` `csv_to_json` `yaml_read` `yaml_write` `data_sample` `data_stats` | 16 |
| **Code Analysis** | `code_search` `code_count` `find_functions` `find_classes` `find_imports` `find_unused_imports` `complexity_check` `code_diff` `format_code` `check_syntax` `find_strings` `find_todos` `dependency_list` `ast_dump` `rename_symbol` `duplicate_finder` | 16 |
| **Docker** | `docker_ps` `docker_images` `docker_run` `docker_exec` `docker_logs` `docker_stop` `docker_start` `docker_rm` `docker_build` `docker_compose` `docker_inspect` `docker_prune` | 12 |
| **Packages** | `pip_install` `pip_uninstall` `pip_list` `pip_show` `pip_freeze` `npm_install` `npm_uninstall` `npm_list` `npm_run` `apt_install` `apt_search` `pkg_info` | 12 |
| **Text** | `regex_match` `regex_replace` `text_replace_bulk` `text_diff` `text_count` `text_extract` `text_transform` `text_wrap` `text_join` `text_sort` `text_dedup` `base64_encode` `base64_decode` `hash_generate` `url_encode` `url_decode` `html_encode` `html_decode` `jwt_decode` `password_generate` `uuid_generate` | 21 |
| **System** | `sys_info` `cpu_info` `memory_info` `disk_info` `process_list` `process_info` `process_kill` `env_list` `env_get` `env_set` `uptime` `whoami` `hostname_info` `os_version` `temp_dir` `shell_info` `python_info` | 17 |
| **Archive** | `zip_create` `zip_extract` `zip_list` `tar_create` `tar_extract` `tar_list` `gzip_compress` `gzip_decompress` `7z_create` `7z_extract` `archive_info` | 11 |
| **Security** | `secret_scan` `vulnerability_scan` `password_strength` `password_generate` `cert_info` `file_permissions` `encrypt_aes` `decrypt_aes` `ip_reputation` `open_ports_check` `hash_crack` `url_safety_check` | 12 |
| **Cloud/DevOps** | `ssh_exec` `scp_transfer` `rsync_sync` `aws_cli` `gcloud_cli` `azure_cli` `terraform_run` `ansible_run` `kubectl_run` `docker_hub_search` | 10 |
| **Workflow** | `pipeline` `watch_file` `retry` `log_write` `log_read` `env_file_load` `env_file_save` `config_read` `config_write` `schedule_cron` `rate_limit` `checksum_verify` | 12 |
| **Notifications** | `send_email` `ntfy_send` `telegram_send` `discord_send` `slack_send` `pushover_send` `gotify_send` `toast_notify` `bark_send` | 9 |
| **Math** | `calculate` `unit_convert` `statistics_calc` `number_base_convert` `matrix_ops` `equation_solve` `percentage_calc` `random_generate` `fibonacci` `prime_check` `factorial` `geometry_calc` `interest_calc` | 13 |
| **AI/LLM** | `text_summarize` `text_translate` `sentiment_analyze` `entity_extract` `keyword_extract` `language_detect` `code_explain` `code_review` `text_classify` `readme_generate` `changelog_generate` `docstring_generate` | 12 |
| **Regex** | `regex_test` `regex_build` `regex_explain` `pattern_find_files` `pattern_count` `log_parse` `csv_parse_regex` `ansi_strip` `html_strip` `markdown_parse` | 10 |
| **Code/Lint** | `lint` `test_runner` `notebook_read` `notebook_edit` `notebook_run` | 5 |
| **Project** | `detect_project` | 1 |
| **Tasks** | `task_create` `task_list` `task_update` `task_delete` | 4 |
| **Scheduling** | `cron_create` `cron_list` `cron_delete` | 3 |
| **Interaction** | `ask_user` | 1 |
| **MCP** | `mcp_list` `mcp_call` | 2 |
| **Monitoring** | `monitor_start` `monitor_status` `monitor_output` `monitor_stop` | 4 |

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
├── tools/                  # 265 built-in tools (30 modules)
│   ├── bash.py             # Shell execution (1 tool)
│   ├── file_ops.py         # File operations (7 tools)
│   ├── git_ops.py          # Git commands (1 tool)
│   ├── git_advanced.py     # Advanced git — blame, search, stash, tag, etc. (13 tools)
│   ├── github.py           # GitHub API (1 tool)
│   ├── web.py              # Web search & fetch (2 tools)
│   ├── image.py            # Image analysis (1 tool)
│   ├── media.py            # Image/video/audio processing + QR (14 tools)
│   ├── doc_reader.py       # Document parsing (1 tool)
│   ├── lint_test.py        # Linting & testing (2 tools)
│   ├── notebook.py         # Jupyter support (3 tools)
│   ├── task_tools.py       # Task management (4 tools)
│   ├── cron_tools.py       # Scheduled jobs (3 tools)
│   ├── ask_user.py         # Interactive prompts (1 tool)
│   ├── monitor.py          # Process monitoring (4 tools)
│   ├── project_detect.py   # Project detection (1 tool)
│   ├── mcp.py              # MCP protocol (2 tools)
│   ├── data.py             # Database, CSV, JSON, YAML (16 tools)
│   ├── network.py          # HTTP, DNS, ports, SSL, download (16 tools)
│   ├── code_analysis.py    # Code search, AST, complexity, diff (16 tools)
│   ├── docker_tools.py     # Docker container management (12 tools)
│   ├── packages.py         # pip, npm, apt package management (12 tools)
│   ├── text.py             # Text processing, encoding, hashing (21 tools)
│   ├── system.py           # System info, processes, env vars (17 tools)
│   ├── archive.py          # ZIP, tar, gzip, 7z (11 tools)
│   ├── security.py         # Security scanning, crypto, secrets (12 tools)
│   ├── cloud.py            # SSH, SCP, rsync, AWS/GCP/Azure/k8s (10 tools)
│   ├── workflow.py         # Pipelines, logging, config, retry (12 tools)
│   ├── notify.py           # Email, Telegram, Discord, Slack, ntfy (9 tools)
│   ├── math_tools.py       # Math, statistics, unit conversion (13 tools)
│   ├── ai_tools.py         # AI summarization, translation, analysis (12 tools)
│   ├── regex_tools.py      # Regex testing, building, parsing (10 tools)
│   └── tokenizer.py        # Token counting (utility)
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

## Update (Existing Users)

If you cloned KEYZBOT before and auto-update isn't working:

```bash
cd ~/KEYZBOT
git fetch origin
git reset --hard origin/master
pip install -r requirements.txt
```

After this, all future updates are fully automatic.

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
