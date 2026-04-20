# Google Workspace Agent

An intelligent, agentic CLI and GUI for Google Workspace automation with a shared execution contract (typed state, structured tool results, reflection-aware retries).

> 🔀 **Repository branch roles:**
> - [`master`](https://github.com/haseeb-heaven/gworkspace-agent/tree/master) — core generic ReAct engine (base)
> - [`crew-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) — CrewAI-powered multi-step Workspace automation
> - [`langchain-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) — LangChain + LangGraph research + compute + Workspace pipeline

---

## Why Three Branches?

| Feature | [`crew-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) | [`langchain-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) |
|---------|----------|--------------| 
| LLM Framework | CrewAI | LangChain + LangGraph |
| Orchestration | ReAct loop (sequential task planner) | LangGraph StateGraph (DAG-based) |
| Internet Web Search | ✅ | ✅ DuckDuckGo / Tavily |
| Sandboxed Code Execution | ✅ | ✅ RestrictedPython sandbox |
| Workspace Automation | ✅ Full | ✅ Full + Google Meet & Chat |
| Telegram Bot Transport | ❌ | ✅ Polling bot with auth |
| Long-Term Memory | ❌ | ✅ Local JSONL + Mem0 |
| Heuristic Fallback (no API key) | ✅ | ✅ |
| Retry / Exponential Backoff | ❌ | ✅ |
| Best For | Professional multi-step automation scripts | Complex research + compute + Workspace workflows |

---

## Architecture

![System Architecture](assets/architecture_diagram.png)

### ReAct Agentic Loop (Both Branches)

The agent follows the **ReAct (Reasoning + Acting)** pattern — a continuous loop where the system **reasons** about what to do next, **acts** on it by calling a tool or API, **observes** the result, and uses that observation to guide the next step. This loop repeats until the entire user request is resolved.

```mermaid
flowchart TD
    A["👤 User Request (CLI/GUI/Telegram)"] --> B["🧠 Planner\nLLM or Heuristic"]
    B --> C["🔍 Executor\nResolve placeholders & context"]
    C --> D["⚡ GWS Runner\nSubprocess call to gws.exe"]
    D --> E["📊 Verification\nTriple-check outcome integrity"]
    E --> F["💾 Memory\nSave episode to JSONL/Mem0"]
    F --> G{"More tasks?"}
    G -->|Yes| C
    G -->|No| H["📋 Output\nFormat results & reply"]

    style A fill:#e94560,color:#fff
    style H fill:#0f3460,color:#fff
```

#### Key Architectural Modules

| Component | Responsibility |
|-----------|----------------|
| **WorkspaceAgentSystem** | Orchestrates planning using LLM (OpenRouter) with a deterministic heuristic fallback. |
| **PlanExecutor** | Resolves dynamic placeholders (`$last_id`), expands batch tasks, and handles artifact injection (Gmail/Drive content). |
| **VerificationEngine** | Multi-layered "Triple-Check" system that verifies API outcomes against expected schemas and side effects. |
| **LongTermMemory** | Multi-layered memory system using local JSONL files and remote Mem0 instances for cross-session context. |
| **GWSRunner** | Executes `gws.exe` with infinite timeout support, transient error retries, and large-argument temporary file handling. |

---

## Key Features

### Core (Both Branches)
- **Dual Framework Support** — Choose CrewAI (crew-ai branch) or LangChain + LangGraph (langchain-ai branch) depending on task complexity.
- **ReAct Agentic Planning** — The LLM reasons, acts, observes, and iterates step-by-step until the full request is resolved.
- **Multi-Layered Memory** — Persistent context across sessions via local JSONL storage or self-hosted Mem0 instances.
- **Triple-Check Verification** — Mandatory validation of every task result to ensure structural and behavioral correctness.
- **Dynamic Placeholder Resolution** — Resolves `$placeholders` across steps (e.g., inject a freshly created spreadsheet ID into the next step's email body).
- **Infinite Timeouts** — Configurable subprocess execution (set `GWS_TIMEOUT_SECONDS=0`) to wait indefinitely for complex tasks.
- **Human-Readable Output** — Formats all API payloads into clean tables and summaries instead of raw JSON.

### LangChain + LangGraph Branch (`langchain-ai`) — Exclusive Features
- **🌐 Internet Web Search** — Built-in DuckDuckGo and Tavily search with LLM-powered summarization.
- **🤖 Telegram Bot Integration** — Secure polling bot transport with Chat ID whitelisting and direct chat fallback for non-GWS queries.
- **💻 Sandboxed Code Execution** — Safely runs Python logic, calculations, and data transformations.
- **🔄 Exponential Backoff & Retry** — Robust reliability layer against rate limits and transient errors.
- **Google Meet & Google Chat** — Extended Workspace service support beyond the base set.
- **LangGraph DAG Orchestration** — Conditional routing between Research, Code, and Workspace API task types.

---

### LangGraph State Machine (`langchain-ai` branch only)

In the `langchain-ai` branch, the ReAct loop is backed by a **LangGraph directed acyclic graph (DAG)** — enabling conditional branching between three task types (web search, code execution, Workspace API) and robust error recovery with retries.

```mermaid
graph TD
    START --> Plan["🧠 Generate Plan"]
    Plan --> Validate["🧪 Validate Tasks"]
    Validate --> Route{"Type of Task?"}

    Route -->|Research| Search["🔍 Web Search"]
    Route -->|Logic/Math| Code["💻 Code Execution"]
    Route -->|Workspace API| Exec["⚡ Execute Task"]

    Search --> Summary["📝 Summarize"]
    Summary --> Update["💾 Update Context"]

    Code --> Update

    Exec --> Success{"Success?"}
    Success -->|Yes| Update
    Success -->|No| Retry["🔄 Handle/Retry"]

    Retry -->|Retry Limit OK| Exec
    Retry -->|Failed| Resp["✅ Final Response"]

    Update --> MoreTasks{"More Tasks?"}
    MoreTasks -->|Yes| Exec
    MoreTasks -->|No| Resp
```

---

## Key Features

### Core (Both Branches)
- **Dual Framework Support** — Choose CrewAI (crew-ai branch) or LangChain + LangGraph (langchain-ai branch) depending on task complexity.
- **ReAct Agentic Planning** — The LLM reasons, acts, observes, and iterates step-by-step until the full request is resolved.
- **Multi-Service Detection** — Detects multiple Google Workspace services in a single natural-language prompt and plans cross-service workflows automatically.
- **Placeholder Resolution** — Dynamically resolves `$placeholders` across steps (e.g., inject a freshly created spreadsheet ID into the next step's email body).
- **Dual Planning Modes** — High-precision LLM reasoning with a zero-API-key deterministic heuristic fallback.
- **Human-Readable Output** — Formats all API payloads into clean tables and summaries instead of raw JSON.
- **Structured Logging** — Logs to both console and rotating `logs/gws_assistant.log` file; includes agent decisions, commands, and errors.

### LangChain + LangGraph Branch (`langchain-ai`) — Exclusive Features
- **🌐 Internet Web Search** — Built-in DuckDuckGo and Tavily search with LLM-powered summarization for real-time data enrichment during task planning.
- **💻 Sandboxed Code Execution** — Safely runs Python logic, calculations, and data transformations inside a `RestrictedPython` environment; no unsafe system access.
- **🔄 Exponential Backoff & Retry** — Robust reliability layer that retries failed Workspace API calls with increasing delays against rate limits and transient errors.
- **Google Meet & Google Chat** — Extended Workspace service support beyond the base set.
- **LangGraph DAG Orchestration** — Conditional routing between Research, Code, and Workspace API task types in a stateful graph.

---

## Supported Placeholders

| Placeholder | Used In | Resolved To |
|------------|---------|-------------|
| `$last_spreadsheet_id` | `sheets.append_values` | ID of the most recently created spreadsheet |
| `$gmail_message_ids` | `gmail.get_message` | Expands to individual message IDs from the search |
| `$gmail_summary_values` | `sheets.append_values` | 2D array of Gmail message data (From, Subject, etc.) |
| `$drive_summary_values` | `sheets.append_values` | 2D array of Drive file data (Name, Type, Link) |
| `$sheet_email_body` | `gmail.send_message` | Formatted text from spreadsheet values |

---

## Supported Services

| Service | Actions | crew-ai | langchain-ai |
|---------|---------|---------|--------------| 
| Gmail | `list_messages`, `get_message`, `send_message` | ✅ | ✅ |
| Google Drive | `list_files`, `create_folder`, `get_file`, `delete_file` | ✅ | ✅ |
| Google Sheets | `create_spreadsheet`, `get_spreadsheet`, `get_values`, `append_values` | ✅ | ✅ |
| Google Calendar | `list_events`, `create_event` | ✅ | ✅ |
| Google Docs | `get_document` | ✅ | ✅ |
| Google Slides | `get_presentation` | ✅ | ✅ |
| Google Contacts | `list_contacts` | ✅ | ✅ |
| Google Meet | — | ❌ | ✅ |
| Google Chat | — | ❌ | ✅ |

---

## Setup

1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Create your env file if needed:

```powershell
Copy-Item .env.example .env
```

3. Run the interactive setup wizard:

```powershell
python .\gws_cli.py --setup
```

The preferred launcher on this branch is `gws_cli.py`. `cli.py` is kept as a compatibility shim.

## Environment Variables

Required or commonly used keys:

- `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`
- `GWS_BINARY_PATH`
- `LANGCHAIN_ENABLED`
- `TAVILY_API_KEY` for higher-quality search fallback
- `CODE_EXECUTION_ENABLED`
- `CODE_EXECUTION_BACKEND` with `restricted_subprocess`, `docker`, or `e2b`
- `E2B_API_KEY` when `CODE_EXECUTION_BACKEND=e2b`
- `DEFAULT_RECIPIENT_EMAIL` for email workflows when the prompt omits a recipient

See `.env.example` for the full template.

## Usage

Run a single task:

```powershell
python .\gws_cli.py --task "List my unread Gmail messages about invoices and save them to a new Google Sheet"
```

Force heuristic mode (no API key required):

```powershell
python .\gws_cli.py --no-langchain --task "Search Drive for quarterly planning docs"
```

Launch Gradio web UI:

```powershell
python .\gws_gradio.py
```

## Example Workflows

**Research + Docs + Sheets + Gmail:**

```text
User: Find the latest Python 3.13 release notes, summarise them into a Google Doc,
      create a tracking Sheet with key changes, and email it to my team.

Agent:
  [1] web_search       → "Python 3.13 release notes"
  [2] summarize        → LLM-powered summary of search results
  [3] docs.create      → Google Doc created with summary
  [4] sheets.create    → Spreadsheet created with key changes table
  [5] gmail.send       → Email sent with Doc + Sheet links attached
```

**Heuristic fallback (no API key):**

```text
User: List my Drive files and append them to an existing spreadsheet.

Agent (heuristic mode):
  [1] drive.list_files        → Lists all Drive files
  [2] sheets.append_values    → Appends file names + links to spreadsheet
                                 using $drive_summary_values placeholder
```

---

## Project Structure

```text
.
├── cli.py                    # Compatibility shim (delegates to gws_cli.py)
├── gws_cli.py                # Main CLI entry point
├── gws_gui.py                # Tkinter GUI launcher
├── gws_gradio.py             # Gradio web UI launcher
├── requirements.txt
├── .env.example              # Environment variable template
└── src/
    └── gws_assistant/
        ├── agent_system.py        # LLM + heuristic planning (ReAct loop core)
        ├── cli_app.py             # Terminal UI with Rich
        ├── config.py              # Environment configuration
        ├── conversation.py        # Orchestration: parsing → planning → execution
        ├── execution.py           # Task expansion, placeholder resolution, context store
        ├── gradio_app.py          # Gradio web interface
        ├── gws_runner.py          # Subprocess runner for gws.exe (with retry/backoff)
        ├── output_formatter.py    # Human-readable output (tables, summaries)
        ├── planner.py             # Command argument construction
        ├── relevance.py           # Post-retrieval relevance scoring & filtering
        ├── service_catalog.py     # Service/action definitions & parameter specs
        ├── setup_wizard.py        # Interactive setup configuration
        │
        │   ── langchain-ai branch only ──
        ├── langchain_agent.py     # LangChain-powered planning engine
        ├── langgraph_workflow.py  # LangGraph StateGraph DAG orchestration
        └── tools/
            ├── web_search.py      # DuckDuckGo / Tavily integration
            └── code_executor.py   # RestrictedPython sandbox
└── tests/
    ├── test_langchain_agent.py    # LangChain planner unit tests
    ├── test_langgraph_workflow.py # LangGraph DAG integration tests
    ├── test_heuristic.py          # Heuristic fallback planner tests
    ├── test_config.py             # Environment config loading tests
    ├── test_retry.py              # GWS runner retry/backoff tests
    └── test_smoke.py              # CLI launcher smoke test
```

---

## Logs

Logs go to both console and `logs/gws_assistant.log` with automatic rotation. The app logs:
- Setup state and binary detection
- Agent planning decisions and LLM reasoning traces
- Actions taken and commands executed
- Context store updates (IDs, URLs, values passed between steps)
- Errors and retry attempts

---

## Tests

```bash
python -m pytest
```

---

## Branches

| Branch | Framework | Extra Capabilities | Link |
|--------|-----------|-------------------|------|
| `master` | CrewAI (base) | Core ReAct Workspace automation | [master](https://github.com/haseeb-heaven/gworkspace-agent/tree/master) |
| `crew-ai` | CrewAI | Full ReAct loop, web search, code execution, multi-service | [crew-ai](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) |
| `langchain-ai` | LangChain + LangGraph | Web Search + Code Sandbox + Retry + Meet & Chat | [langchain-ai](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) |

---

## Changelogs
For changelogs check [CHANGELOG](https://github.com/haseeb-heaven/gworkspace-agent/blob/master/CHANGELOG.md)

## License

This project is licensed under the **MIT License**.

## Author
This project is created and maintained by [Haseeb-Heaven](https://www.github.com/haseeb-heaven).
