# Google Workspace Agent

An intelligent, agentic CLI and GUI for Google Workspace automation powered by a hybrid **LangChain + LangGraph** architecture. Transforms natural language requests into complex, multi-step workflows across Gmail, Drive, Sheets, Docs, Calendar, and more — with ReAct planning, sandboxed code execution, and long-term memory.

> 🔀 **Branch roles:**
> - [`master`](https://github.com/haseeb-heaven/gworkspace-agent/tree/master) — core generic ReAct engine (base)
> - [`crew-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) — CrewAI-powered multi-step Workspace automation
> - [`langchain-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) — LangChain + LangGraph research + compute + Workspace pipeline
> - [`develop`](https://github.com/haseeb-heaven/gworkspace-agent/tree/develop) — active development branch (latest features)

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [Interfaces](#interfaces)
  - [CLI — Terminal Interface](#1-cli--terminal-interface)
  - [Python Desktop GUI — gws_gui.py](#2-python-desktop-gui--gws_guipy)
  - [Web-based GUI — gws_gui_web.py](#3-web-based-gui--gws_gui_webpy)
  - [Telegram Bot](#4-telegram-bot)
- [Running Tests](#running-tests)
- [Example Workflows](#example-workflows)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Supported Services](#supported-services)
- [Troubleshooting](#troubleshooting)
- [Branch Comparison](#branch-comparison)

---

## 🚀 Getting Started

To set up the Google Workspace Agent, including Google Cloud credentials and the required CLI tools, please refer to the detailed guide:

👉 **[Read the SETUP.md Guide](./SETUP.md)**

---

## 🛡️ Safety & Modes (New!)

The agent is designed to be **Safe by Default**. It intercepts operations that could modify or delete your data.

### Read-Only Mode (Default: True)
Blocks all write, create, update, append, send, and delete actions.
*   **To disable (allow writes):** Run with `--read-write` or set `READ_ONLY_MODE=false` in `.env`.

### Sandbox Mode (Default: True)
When writes are allowed (`--read-write`), Sandbox mode intercepts any state-changing action and prompts for user confirmation `(Y/N)` before executing.
*   **To disable (run autonomously):** Run with `--no-sandbox` or set `SANDBOX_ENABLED=false` in `.env`.

### Configuration Precedence
1. **CLI Flags** (`--sandbox` / `--read-write`) have the highest priority.
2. **Environment Variables** (`SANDBOX_ENABLED` / `READ_ONLY_MODE` in `.env`) are used if no flags are provided.
3. **Hardcoded Defaults** are used if `.env` is empty (Defaults to `True` for both).

---

## Interfaces

The agent supports four interfaces. All of them read from the same `.env` configuration.

---

### 1. CLI — Terminal Interface

The primary interface. Rich terminal UI with interactive prompts, formatted output tables, and real-time streaming.

#### Launch (interactive mode)

```bash
python gws_cli.py
```

#### Launch (single task mode)

```bash
python gws_cli.py --task "Search Drive for all .qvm files, count them, build a table, and email it to me"
```

#### CLI Demo

![CLI Demo](assets/cli_demo.png)

#### Available flags

| Flag | Description |
|---|---|
| `--task "..."` | Run a single task and exit |
| `--setup` | Run the interactive setup wizard |
| `--no-langchain` | Disable LLM — use heuristic planner only |
| `--save-output FILE` | Append all output to a file |
| `--read-write` | Disable read-only mode for the session |
| `--no-sandbox` | Disable interactive confirmation prompts |

---

### 2. Python Desktop GUI — gws_gui.py

A native desktop application built with `CustomTkinter`. It provides a structured way to analyze natural language requests, select GWS services/actions manually, and view formatted execution logs in a dark-themed window.

#### Launch

```bash
python gws_gui.py
```

#### Python GUI Demo

![Desktop GUI Demo](assets/gui_desktop_demo.png)

#### Features
- **Analyze Request**: Automatically detects the intended service and action from your text.
- **Manual Overrides**: Fine-tune the detected parameters or select actions from dropdowns.
- **Real-time Console**: Watch the raw `gws` commands and API responses as they happen.

> ℹ️ Requires a display environment. Will not work over SSH without X forwarding.

---

### 3. Web-based GUI — gws_gui_web.py

A modern, browser-based chat interface powered by `Gradio`. Ideal for quick research tasks, remote access, and sharing the agent's capabilities via a public URL.

#### Launch (local)

```bash
python gws_gui_web.py
```

Then open: [http://localhost:7860](http://localhost:7860)

#### Web GUI Demo

![Web GUI Demo](assets/gui_web_demo.png)

#### Launch (public share link)

```bash
python gws_gui_web.py --share
```

#### Run with Docker

```bash
docker build -t gws-agent .
docker run -p 8080:8080 \
  -e OPENROUTER_API_KEY=your_key \
  -e GWS_BINARY_PATH=/usr/local/bin/gws \
  gws-agent
```

---

### 4. Telegram Bot

A secure Telegram bot interface. Only responds to a whitelisted Chat ID set in `.env`. It spawns a background `gws_cli.py` process for every request.

#### Launch

```bash
python gws_telegram.py
```

> ⚠️ The bot rejects all messages from chat IDs that do not match `TELEGRAM_CHAT_ID`.

---

## Running Tests

```bash
python -m pytest
```

> ℹ️ Unmarked tests are deselected by default. Run `python -m pytest -m ""` to include live integration tests.

---

## Example Workflows

### Research → Docs → Sheets → Email

```text
Input: "Find the latest Python 3.13 release notes, write a summary to a Google Doc,
        create a tracking Sheet with key changes, and email both links to my team."

Plan:
  [1] web_search        → "Python 3.13 release notes"
  [2] docs.create       → Google Doc with summary
  [3] sheets.create     → Spreadsheet with key changes table
  [4] gmail.send        → Email with Doc + Sheet links
```

---

## Architecture

### ReAct Agentic Loop

```mermaid
flowchart TD
    A["👤 User Request (CLI / GUI / Web / Telegram)"] --> B["🧠 Planner\nLLM (OpenRouter) or Heuristic fallback"]
    B --> C["🔍 Executor\nResolve placeholders & context"]
    C --> D["⚡ GWS Runner\nSubprocess call to gws binary"]
    D --> E["📊 Verification\nTriple-check outcome integrity"]
    E --> F["💾 Memory\nSave episode to JSONL / Mem0"]
    F --> G{"More tasks?"}
    G -->|Yes| C
    G -->|No| H["📋 Output\nFormat and return results"]
