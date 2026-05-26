<p align="center">
  <br>
  <strong>KEYZBOT</strong>
  <br>
  <sub>v9.0 &mdash; Full AI Coding Agent</sub>
</p>

<p align="center">
  <code>34 tools</code> &bull;
  <code>multimodal chat</code> &bull;
  <code>web UI</code> &bull;
  <code>termux native</code>
</p>

---

## Features

- **Auto-update** — checks GitHub on every startup, pulls and restarts if new version exists
- **34 built-in tools** — bash, file ops, git, web search, image reading, scheduling, and more
- **Multimodal chat** — upload images with text, AI can see and analyze them
- **Image compression** — auto-resize to 1024px JPEG 70% before sending to API
- **Web UI** — polished dark theme with streaming, chat history, tool panels
- **Multi-chat** — create, switch, rename, delete conversations
- **Session persistence** — messages survive refresh, restore on reconnect
- **Sub-agents** — fork background agents for parallel tasks
- **Plan & tasks** — structured planning with task tracking
- **Memory system** — remember/recall/forget across sessions
- **Streaming resilience** — server continues processing on disconnect
- **CLI + Web** — run from terminal or browser

## Tools

| Category | Tools |
|----------|-------|
| System | `bash`, `file_ops`, `monitor` |
| Code | `git_ops`, `github`, `lint_test`, `notebook` |
| Web | `web` (search/extract), `doc_reader` |
| Media | `image` (read/analyze) |
| Project | `project_detect`, `tokenizer` |
| Productivity | `task_tools`, `cron_tools`, `ask_user` |
| Extensions | `mcp` (Model Context Protocol), plugins |

## Install on Termux

### 1. Install Termux

Download from **F-Droid** (recommended, not Play Store):

```
https://f-droid.org/packages/com.termux/
```

### 2. Setup Termux

```bash
pkg update && pkg upgrade -y
pkg install python git -y
```

### 3. Clone & Install

```bash
git clone https://github.com/mygeminim-source/KEYZBOT.git
cd KEYZBOT
pip install -r requirements.txt
bash install.sh
```

### 4. Configure API

Edit `config.json` with your API provider:

```json
{
  "base_url": "https://your-provider.com/v1",
  "model": "your-model",
  "api_key": "your-api-key",
  "max_tokens": 4096,
  "temperature": 0.7,
  "system_prompt": "You are KEYZBOT, a helpful AI assistant."
}
```

Or edit `providers.json` to add multiple providers:

```json
{
  "providers": [
    {
      "id": "my-provider",
      "api_key": "sk-xxx",
      "base_url": "https://api.example.com/v1",
      "model": "model-name"
    }
  ],
  "active": "my-provider"
}
```

### 5. Run

**CLI mode:**
```bash
keyzbot
```

**Web UI mode:**
```bash
python3 web/server.py
```
Then open `http://localhost:8080` in your browser.

## Requirements

- Python 3.8+
- Termux (Android) or any Linux shell
- API key from any OpenAI-compatible provider (Groq, SambaNova, Cerebras, OpenRouter, etc.)

## Usage

```
keyzbot                     # start CLI
keyzbot "fix the bug"       # one-shot query
keyzbot /tools              # list tools
keyzbot /model groq         # switch provider
```

**Web UI commands:**
```
/clear        clear chat
/model        change model/provider
/tools        list tools
/export       export chat (json/text/markdown)
/fast         toggle fast mode
```

## Project Structure

```
KEYZBOT/
  keyzbot.py          # CLI entry point
  config.json         # API configuration
  providers.json      # multi-provider config
  core/
    agent.py          # AI agent loop
    config.py         # config & history management
    tools.py          # tool router
    web_sessions.py   # session persistence
    ...
  tools/
    bash.py           # shell execution
    file_ops.py       # read/write/edit files
    web.py            # web search & fetch
    image.py          # image reading
    ...
  web/
    server.py         # Flask + SocketIO server
    static/
      app.js          # web UI client
      style.css       # dark theme styles
      index.html      # web UI page
```

## License

MIT

---

<p align="center">
  Built by <strong>WAHYU FAOSZAN MUZAQI</strong> &bull; 2024&ndash;2026
</p>
