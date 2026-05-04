# 🚀 Google Workspace Agent

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/release/python-3119/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: LangGraph](https://img.shields.io/badge/Framework-LangGraph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-ReAct-blueviolet.svg)](https://python.langchain.com/)
[![Safety: Sandbox](https://img.shields.io/badge/Safety-Sandboxed-green.svg)](#safety--security)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](https://pytest.org/)
[![CI/CD](https://github.com/haseeb-heaven/gworkspace-agent/actions/workflows/pipeline.yml/badge.svg)](https://github.com/haseeb-heaven/gworkspace-agent/actions/workflows/pipeline.yml)</br>
An autonomous AI agent for Google Workspace, built on a hybrid **LangChain ReAct + LangGraph DAG** architecture. It converts natural language into verified, multi-step workflows across Gmail, Drive, Sheets, Docs, Calendar, and 15+ other Google services — with built-in safety, memory, and sandboxed code execution.

---

## Table of Contents

- [Key Features](#key-features)
- [Demos](#demos)
- [Architecture](#architecture)
- [LangGraph DAG](#langgraph-dag)
- [ReAct Loop](#react-loop)
- [Supported Services](#supported-services)
- [Getting Started](#getting-started)
- [Interfaces](#interfaces)
- [Configuration](#configuration)
- [Safety & Security](#safety--security)
- [Testing](#testing)
- [Contributing](#contributing)

---

## Version
Latest: **v0.9.1**  
See [CHANGELOG.md](CHANGELOG.md) for full version history.

---

## Key Features

- **5-Step Verification Engine** - Strict, non-bypassable verification system with severity levels (CRITICAL, ERROR, WARNING) that validates parameters, permissions, results, data integrity, and idempotency
- **Hybrid ReAct + LangGraph Engine** — LLM-driven planner generates a typed DAG of tasks; LangGraph executes nodes with full state persistence and smart retry logic
- **Multi-Service Orchestration** — a single natural language request can chain Gmail, Drive, Sheets, Docs, Calendar, and Code execution in one plan
- **Long-Term Memory via Mem0** — agent learns from past interactions and recalls user preferences across sessions
- **Sandboxed Code Execution** — Python code runs inside a restricted E2B sandbox with stdout/stderr capture and exit code tracking
- **Safety-by-Default** — Read-Only mode blocks all writes; Sandbox mode requires manual confirmation before any state-changing action
- **Multi-Interface** — CLI, Desktop GUI, Web (Gradio), and Telegram Bot all share the same agent core
- **Model Agnostic** — works with any OpenAI-spec tool-calling model (Gemini, GPT-4o, Claude, Mistral, LLaMA) via OpenRouter or direct APIs
- **Verified Tool-Calling** — `model_registry.py` validates that the configured model supports function calling before any plan is generated

---

---

## 🎬 Demos & Showcases

### ⚡ Live Previews
The following animated showcases demonstrate the agent's autonomous planning and multi-service execution in real-time.

| Autonomous Workflow Demo | Multi-Interface Simulation |
| :---: | :---: |
| ![Animated Demo](assets/demo_animated.svg) | ![Simulation](assets/simulation_animated.svg) |

> **Dynamic Multi-Mode Preview:** The simulation on the right is automatically generated and cycles through the CLI, Desktop, and Web interfaces.

### 🖼️ Interface Gallery
Detailed snapshots of the available user interfaces.

#### 💻 CLI (Typer + Rich)
![CLI Demo](assets/cli_demo.png)

#### 🖥️ Desktop GUI
![Desktop GUI Demo](assets/gui_desktop_demo.png)

#### 🌐 Web Interface (Gradio)
![Web GUI Demo](assets/gui_web_demo.png)

### Architecture Diagram
![Architecture](assets/architecture_diagram.png)

---

## Architecture

The agent uses a **three-layer architecture**: an LLM Planner that reasons about intent, a LangGraph Workflow that manages stateful execution, and a GWS Executor that calls real Google APIs.

```mermaid
---
id: 381d8783-6e2b-46fa-b5fa-879171ca0dbf
---
flowchart TD
    USER["👤 User Request"] --> AGENT

    subgraph AGENT["🤖 Agent System"]
        PL["🧠 Planner LLM → TaskPlan DAG"]
        WF["⚙️ LangGraph Workflow generate → execute → reflect"]
    end

    AGENT --> EX

    subgraph EX["⚡ Execution Engine"]
        direction LR
        RS["Resolver"] --> EXC["Executor"] --> CU["Context Updater"] --> VF["Verifier"]
    end

    EX --> APIS

    subgraph APIS["☁️ Google Workspace APIs"]
        direction LR
        GM["Gmail"] --- DR["Drive"] --- SH["Sheets"] --- DC["Docs"] --- CA["Calendar"]
    end

    AGENT <--> SUP

    subgraph SUP["🛡️ Support"]
        direction LR
        MEM["Memory\nMem0"] --- SG["Safety\nGuard"] --- MR["Model\nRegistry"]
    end

    style AGENT fill:#1a1a2e,color:#fff,stroke:#4A90D9
    style EX fill:#0f3460,color:#fff,stroke:#E67E22
    style APIS fill:#16213e,color:#fff,stroke:#2ECC71
    style SUP fill:#1a1a2e,color:#fff,stroke:#8E44AD
```
---

## LangGraph DAG

The agent's execution graph is a **stateful directed acyclic graph** with four core nodes and conditional edges. Each node operates on a shared `AgentState` object that persists across the entire request lifecycle.

```mermaid
flowchart TD
    START(["▶ START"]) --> GP

    GP["🧠 generate_plan\nLLM generates TaskPlan\nwith typed task list\nand service/action pairs"]

    GP --> ET

    ET["⚡ execute_task\n① Resolver expands $placeholders\n② Executor calls GWS API\n③ ContextUpdater writes outputs\n④ Verifier checks integrity"]

    ET --> RN

    RN{"🔍 reflect_node\nAll tasks done?\nAny errors?"}

    RN -->|"more tasks remaining"| ET
    RN -->|"transient error → retry"| GP
    RN -->|"AUTH / NOT_FOUND → skip"| FO
    RN -->|"all tasks complete"| FO

    FO["📋 format_output\nApply output_formatter\nBuild final response string"]

    FO --> END(["⏹ END"])

    style GP fill:#4A90D9,color:#fff,stroke:#2c6fad
    style ET fill:#27AE60,color:#fff,stroke:#1a7a43
    style RN fill:#E67E22,color:#fff,stroke:#b85e0a
    style FO fill:#8E44AD,color:#fff,stroke:#6b2f87
    style START fill:#2ECC71,color:#fff,stroke:#27ae60
    style END fill:#E74C3C,color:#fff,stroke:#c0392b

```

---

### AgentState Schema

python
class AgentState(TypedDict):
    user_request:   str            # original natural language query
    task_plan:      list[Task]     # planned task list generated by LLM
    context:        dict           # shared execution context (placeholders live here)
    task_results:   dict           # keyed outputs per task ID e.g. task-1, task-2
    current_index:  int            # execution cursor pointing to current task
    error:          str | None     # last error string for reflect_node classification
    retry_count:    int            # retry counter — capped per task to prevent loops
    final_output:   str            # formatted final response string


---

## ReAct Loop

Each task execution follows the **ReAct (Reason → Act → Observe)** pattern:

```mermaid
flowchart LR
    R["REASON<br>Planner reads user intent<br>+ service catalog 100+ actions<br>+ Mem0 conversation memory<br>→ generates typed TaskPlan JSON"]
    A["ACT<br>For each Task in plan:<br>① Resolver expands $placeholders<br>② Task validated vs model registry<br>③ GWS API called via executor<br>④ Result written to shared context"]
    O["OBSERVE<br>Verifier checks output integrity<br>Reflect node classifies errors<br>AUTH/NOT_FOUND → skip<br>SERVER/UNKNOWN → retry<br>Memory updated with outcome"]

    R --> A --> O --> R
```

---

## Supported Services

The agent orchestrates **20+ Google services** and **100+ actions** via `service_catalog.py`:

| Service | Key Actions |
|---|---|
| 📧 **Gmail** | send, read, search, reply, forward, label, delete messages |
| 📂 **Drive** | list, upload, download, export, move, delete, share files and folders |
| 📊 **Sheets** | create, read, append, update, format spreadsheets |
| 📝 **Docs** | create, read, batch-update documents |
| 📅 **Calendar** | create, list, update, delete events with reminders |
| 📽️ **Slides** | create and read presentations |
| 👥 **Contacts** | list, search, create contacts |
| 💬 **Chat** | send messages to Google Chat spaces |
| 🐍 **Code** | execute Python in E2B sandbox, capture stdout/stderr/exit code |
| 🔍 **Web Search** | search and summarize web results |
| 🧠 **Memory** | store and retrieve user preferences via Mem0 |
| 🛡️ **Admin SDK** | manage users, groups, org units |
| 📜 **Apps Script** | run Google Apps Scripts |
| 🔐 **Model Armor** | content safety screening |
| 📋 **Tasks** | manage Google Tasks lists |
| 🗒️ **Keep** | create and read Google Keep notes |
| 📝 **Forms** | create and read Google Forms |
| 👥 **Meet** | create Meet links |
| 🏫 **Classroom** | manage courses and assignments |

---

## Getting Started

To get the agent running on your local machine, please follow the comprehensive **[Setup Guide (SETUP.md)](SETUP.md)**.

### Quick Start
1. **Clone & Install:**
   ```bash
   git clone https://github.com/haseeb-heaven/gworkspace-agent.git
   cd gworkspace-agent
   pip install -e .
   ```
2. **Configure Credentials:** Follow the [Google Cloud Setup](SETUP.md#%EF%B8%8F-step-3-google-cloud--credentials-setup) instructions.
3. **Run the Agent:**
   ```bash
   python gws_cli.py --task "List my drive files"
   ```

---

## Interfaces

| Interface | Command | Description |
|---|---|---|
| **💻 CLI** | `python gws_cli.py` | Rich terminal UI with streaming output, tables, and interactive prompts |
| **🖥️ Desktop GUI** | `python gws_gui.py` | Native app with visual task logs and manual controls |
| **🌐 Web UI** | `python gws_gui_web.py` | Gradio chat interface accessible from any browser |
| **🤖 Telegram Bot** | `python gws_telegram.py` | Secure mobile access via whitelisted Telegram Bot API |

---

## Configuration

All system configuration (API keys, security modes, and service endpoints) is managed via the `.env` file. 

> [!IMPORTANT]
> Detailed configuration steps and a full environment variable reference can be found in the **[Configuration Section of SETUP.md](SETUP.md#%EF%B8%8F-step-5-agent-configuration)**.

---

## Safety & Security

```mermaid
flowchart TD
    REQ["Incoming Task"] --> RO{"Read-Only Mode\nON by default"}
    RO -->|"write / delete / send action"| BLOCK["🚫 Blocked\nAction rejected immediately"]
    RO -->|"read-only action"| SB{"Sandbox Mode\nON by default"}
    SB -->|"state-changing action"| CONF{"User Confirmation\nY / N prompt"}
    CONF -->|"N"| SKIP["⏭ Skipped"]
    CONF -->|"Y"| EXEC["✅ Execute"]
    SB -->|"safe read action"| EXEC
    RO -->|"--read-write flag set"| SB

    style BLOCK fill:#E74C3C,color:#fff
    style SKIP fill:#E67E22,color:#fff
    style EXEC fill:#27AE60,color:#fff
```

- **Read-Only Mode** — default ON. Enable writes with `--read-write` or `READ_ONLY_MODE=false`
- **Sandbox Mode** — default ON. Disable with `--no-sandbox` or `SANDBOX_ENABLED=false`
- **Email Recipient Lock** — `DEFAULT_RECIPIENT_EMAIL` forces all outbound emails to one address regardless of what the LLM generates
- **Model Registry** — raises `ValueError` at startup if the configured model is not on the tool-calling allowlist in `model_registry.py`

---

## Testing

```bash
# Full test suite
python -m pytest
```

```bash
# Drive metadata and placeholder contract tests only
python -m pytest -m "drive" -v
```

```bash
# With coverage report
python -m pytest --cov=gws_assistant --cov-report=term-missing
```

```bash
# Integration tests (requires live Google credentials)
python -m pytest -m "not skip_integration" -v
```

| Test File | Coverage |
|---|---|
| `tests/test_placeholder_contracts.py` | Canonical and legacy placeholder resolution |
| `tests/test_drive_metadata.py` | Drive file summarizer helper |
| `tests/test_resolver.py` | Full resolver logic including LEGACY_MAP |

---

## Contributing

1. Fork the repository
2. Branch from `develop`: `git checkout -b feature/your-feature develop`
3. Make changes with tests
4. Ensure all tests pass: `python -m pytest`
5. Open a Pull Request targeting **`develop`** — never target `master` directly

---

## License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

> **Note:** This project was **architected and designed** by **Haseeb Mir**.
> AI tools (GitHub Copilot, Jules) were used to assist with **implementation**,
> **boilerplate generation**, and **refactoring** — all **features**, **architecture**
> **decisions**, and **system design** are **original**.

<p align="center">
  Built with ❤️ by <a href="https://github.com/haseeb-heaven">Haseeb Mir</a>
</p>
