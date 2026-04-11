# Google Workspace Agent

An intelligent, agentic CLI and GUI for Google Workspace automation powered by a **dual-framework LLM-driven ReAct planning loop** — choose between **CrewAI** (lightweight, fast) or **LangChain + LangGraph**.

> 🔀 **Two specialized branches are available:**
> - [`crew-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) — CrewAI-based agent: fast, lightweight, multi-step Workspace automation
> - [`langchain-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) — LangChain + LangGraph agent: full-power with **internet web search** + **sandboxed code execution**

---

## Why Two Branches?

| Feature | [`crew-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) | [`langchain-ai`](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) |
|---------|----------|--------------|
| LLM Framework | CrewAI | LangChain + LangGraph |
| Orchestration | ReAct loop (sequential task planner) | LangGraph StateGraph (DAG-based) |
| Internet Web Search | ❌ | ✅ DuckDuckGo / Tavily |
| Sandboxed Code Execution | ❌ | ✅ RestrictedPython sandbox |
| Workspace Automation | ✅ Full | ✅ Full + Google Meet & Chat |
| Heuristic Fallback (no API key) | ✅ | ✅ |
| Retry / Exponential Backoff | ❌ | ✅ |
| Best For | Fast, reliable Workspace-only tasks | Complex research + compute + Workspace workflows |

---

## Architecture

![System Architecture](assets/architecture_diagram.png)

### ReAct Agentic Loop (Both Branches)

The agent follows the **ReAct (Reasoning + Acting)** pattern — a continuous loop where the system **reasons** about what to do next, **acts** on it by calling a tool or API, **observes** the result, and uses that observation to guide the next step. This loop repeats until the entire user request is resolved.

```mermaid
flowchart LR
    A["👤 User Request"] --> B["🔍 Observe\nParse intent & detect services"]
    B --> C["🧠 Reason\nLLM plans multi-step tasks"]
    C --> D["⚡ Act\nExecute task via gws.exe"]
    D --> E["📊 Observe\nParse result · update context"]
    E --> F{"More tasks?"}
    F -->|Yes| G["🧠 Reason\nResolve placeholders\nwith prior context"]
    G --> D
    F -->|No| H["🔍 Filter\nRelevance scoring"]
    H --> I["📋 Format\nHuman-readable output"]
    I --> J["✅ Present to User"]

    style A fill:#e94560,color:#fff
    style J fill:#0f3460,color:#fff
```

#### ReAct Loop — Step-by-Step

| Step | Component | What Happens |
|------|-----------|--------------|
| 1 | **Intent Parser** | Detects which Google services (Gmail, Drive, Sheets, etc.) are mentioned |
| 2 | **LLM Planner** | CrewAI or LangChain agent decomposes the request into an ordered list of tasks with parameters and `$placeholder` variables |
| 3 | **Task Expander** | Resolves `$placeholders` (e.g., `$last_spreadsheet_id` → actual ID from prior step) and expands batch operations |
| 4 | **GWS Runner** | Executes each command as a subprocess call to `gws.exe` with proper argument encoding |
| 5 | **Context Store** | After each task, extracts key IDs, URLs, and values; stores them for downstream tasks |
| 6 | **Relevance Filter** | Scores each result against original query keywords; drops items below relevance threshold |
| 7 | **Output Formatter** | Converts raw API payloads into clean tables, summaries, and human-readable text |

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

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run setup explicitly:

```bash
python cli.py --setup
```

Setup mode:
- Detects a local, npm/global, or PATH-provided `gws` binary.
- Saves the resolved `GWS_BINARY_PATH`.
- Saves OpenAI or OpenRouter model settings.
- Saves API keys if provided (including optional Tavily key for `langchain-ai` branch web search).
- Writes `.env`.

> Setup is **never triggered automatically**. Normal app startup expects setup to already be complete.

---

## Run

Default CLI:

```bash
python cli.py
```

Backward-compatible launcher:

```bash
python gws_cli.py
```

GUI (Tkinter):

```bash
python gws_gui.py
```

Browser GUI (Gradio):

```bash
python gws_gradio.py --host 127.0.0.1 --port 7860
```

Legacy / No-LLM fallback (`langchain-ai` branch):

```bash
python cli.py --no-langchain --task "Search Drive for projects"
```

Optional output capture:

```bash
python cli.py --save-output outputs/session.txt
```

---

## Example Requests

**Simple search:**
```text
>: List all emails from boss@company.com
```

**Multi-service workflow:**
```text
>: Search Google Documents for "Agentic AI - Builders" and create a Sheet
   from the results, then send email to user@example.com with the sheet link
```

The agent plans this as:
1. Search Drive for documents matching "Agentic AI - Builders" (with query filter).
2. Create a Google Sheet titled "Agentic AI Builders Data".
3. Append the filtered Drive results into the sheet.
4. Send an email with the sheet link automatically injected.

**Research + Workspace workflow (`langchain-ai` branch):**
```text
>: Search the web for the latest AI tools released this week and save a summary to a new Google Sheet
```

The agent routes this as:
1. Web search via DuckDuckGo/Tavily for "latest AI tools this week".
2. LLM summarizes the search results.
3. Create a Google Sheet and append the summarized data.

**Code + Workspace workflow (`langchain-ai` branch):**
```text
>: Calculate the total revenue from my last 10 Gmail invoice emails and write the result to a Sheet
```

The agent routes this as:
1. `gmail.list_messages` + `gmail.get_message` × 10 to extract invoice data.
2. Run sandboxed Python to sum the values.
3. `sheets.create_spreadsheet` + `sheets.append_values` with the result.

If no Workspace service is detected:
```text
No Google Workspace service detected in your request.
```

---

## Project Structure

```text
.
├── cli.py                    # Main CLI entry point
├── gws_cli.py                # Backward-compatible launcher
├── gws_gui.py                # Tkinter GUI launcher
├── gws_gradio.py             # Gradio web UI launcher
├── requirements.txt
└── src/
    └── gws_assistant/
        ├── agent_system.py        # LLM + heuristic planning (ReAct loop core)
        ├── cli_app.py             # Terminal UI with Rich
        ├── config.py              # Environment configuration
        ├── conversation.py        # Orchestration: parsing → planning → execution
        ├── execution.py           # Task expansion, placeholder resolution, context store
        ├── gradio_app.py          # Gradio web interface
        ├── gws_runner.py          # Subprocess runner for gws.exe
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
| `main` | CrewAI (base) | Core ReAct Workspace automation | [main](https://github.com/haseeb-heaven/gworkspace-agent) |
| `crew-ai` | CrewAI | Full ReAct loop, multi-service | [crew-ai](https://github.com/haseeb-heaven/gworkspace-agent/tree/crew-ai) |
| `langchain-ai` | LangChain + LangGraph | Web Search + Code Sandbox| [langchain-ai](https://github.com/haseeb-heaven/gworkspace-agent/tree/langchain-ai) |

---

## Changelogs
For changelogs check [CHANGELOG](https://github.com/haseeb-heaven/gworkspace-agent/CHANGELOG.md)

## License

This project is licensed under the **MIT License**.

## Author
This project is created and maintained by [Haseeb-Heaven](www.github.com/haseeb-heaven).