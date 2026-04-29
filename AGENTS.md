# AGENTS.md — GWorkspace Agent

> This file is read automatically by **@google-labs-jules** and other AI coding agents.
> It describes the architecture, agents, tools, conventions, and CI rules of this repository.
> Keep this file up to date whenever you add new agents, tools, or change key workflows.

---

## Project Overview

**GWorkspace Agent** is a LangGraph-powered AI assistant for Google Workspace (Gmail, Drive, Calendar, Docs, Sheets, Slides, Meet, Chat). It accepts natural language commands and translates them into Google Workspace API calls using a multi-agent planning and execution pipeline.

- **Primary Language:** Python 3.11
- **Core Framework:** LangGraph + LangChain
- **LLM Backend:** OpenAI-compatible API (configurable via `LLM_PROVIDER` / `LLM_MODEL`)
- **Interfaces:** CLI, Desktop GUI (Tkinter), Web UI (Gradio), Telegram Bot, Cloud Run (REST)
- **Deployment:** Google Cloud Run via Docker

---

## Repository Structure

```
gworkspace-agent/
├── gws_assistant/               # Core agent package
│   ├── agent_system.py          # Multi-agent orchestration (Planner + Executor + Verifier)
│   ├── planner.py               # Task planning agent — decomposes user intent into steps
│   ├── intent_parser.py         # NLU layer — parses raw user input into structured intents
│   ├── langgraph_workflow.py    # LangGraph state machine — primary agentic workflow
│   ├── langchain_agent.py       # LangChain ReAct agent — alternative execution backend
│   ├── service_catalog.py       # Registry of all 60+ Google Workspace tool definitions
│   ├── verification_engine.py   # Post-execution verifier — validates outputs against intent
│   ├── safety_guard.py          # Safety layer — blocks destructive/irreversible actions
│   ├── execution/               # Execution layer — runs GWS binary tool calls
│   ├── tools/                   # Individual GWS tool wrappers (Gmail, Drive, Calendar, etc.)
│   ├── llm_client.py            # LLM abstraction — supports OpenAI, Anthropic, OpenRouter
│   ├── config.py                # AppConfig — loads and validates all environment variables
│   ├── model_registry.py        # Tool-capable model registry + fallback chain
│   ├── memory.py                # Short-term conversation memory
│   ├── memory_backend.py        # Long-term persistent memory backend
│   ├── models.py                # Pydantic data models (AgentTask, Intent, PlanStep, etc.)
│   ├── output_formatter.py      # Formats agent responses for each interface (CLI/GUI/API)
│   ├── relevance.py             # Relevance scoring — filters tool results by intent
│   ├── drive_query_builder.py   # Builds Drive API query strings from natural language
│   ├── gmail_query_builder.py   # Builds Gmail search query strings from natural language
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── logging_utils.py         # Structured logging setup
│   ├── cli_app.py               # CLI interface entrypoint
│   ├── gui_app.py               # Desktop GUI (Tkinter) interface
│   ├── gradio_app.py            # Web UI (Gradio) interface
│   ├── telegram_app.py          # Telegram Bot interface
│   ├── gws_runner.py            # GWS binary runner — subprocess wrapper for GWS CLI tool
│   ├── setup_wizard.py          # First-run setup wizard
│   └── chat_utils.py            # Shared chat helper utilities
├── gws_cli.py                   # CLI entrypoint (calls cli_app.py)
├── gws_gui.py                   # GUI entrypoint (calls gui_app.py)
├── gws_gui_web.py               # Web entrypoint (calls gradio_app.py)
├── gws_telegram.py              # Telegram entrypoint (calls telegram_app.py)
├── tests/                       # All tests (unit + integration + live)
├── framework/                   # Internal framework utilities
├── scripts/                     # Setup and utility scripts
├── .github/workflows/           # CI/CD pipeline (pipeline.yml)
├── Dockerfile                   # Production Docker image
├── Dockerfile.sandbox           # Sandbox Docker image for safe execution
├── requirements.txt             # Python dependencies
└── pyproject.toml               # Package metadata and tool config
```

---

## Core Agents

### 1. Planner Agent
- **File:** `gws_assistant/planner.py`
- **Role:** Receives a parsed user intent and decomposes it into an ordered list of `PlanStep` objects. Each step maps to a specific GWS tool.
- **Input:** `Intent` object (from `intent_parser.py`)
- **Output:** `List[PlanStep]` — ordered execution plan
- **Key constraint:** Only emits steps for tools registered in `service_catalog.py`. Never invents tool names.

### 2. Executor Agent (LangGraph Workflow)
- **File:** `gws_assistant/langgraph_workflow.py`
- **Role:** State machine that executes each `PlanStep` sequentially. Handles retries, fallback models, and partial failures.
- **State schema:** Defined in `models.py` as `WorkflowState`
- **Nodes:** `parse_intent → plan → execute_step → verify → respond`
- **LLM calls:** Uses `llm_client.py` with automatic fallback chain from `model_registry.py`

### 3. LangChain ReAct Agent
- **File:** `gws_assistant/langchain_agent.py`
- **Role:** Alternative execution backend using LangChain's ReAct loop. Used when `USE_LANGCHAIN=true`.
- **Tools:** Dynamically loaded from `gws_assistant/tools/`
- **Memory:** Integrates with `memory.py` for conversation context

### 4. Verification Engine
- **File:** `gws_assistant/verification_engine.py`
- **Role:** Post-execution validator. Checks whether the tool outputs actually satisfy the original user intent. Triggers re-planning if verification fails.
- **Input:** `Intent` + `List[ToolResult]`
- **Output:** `VerificationResult` (passed / failed / needs_retry)

### 5. Safety Guard
- **File:** `gws_assistant/safety_guard.py`
- **Role:** Pre-execution safety layer. Blocks or requires confirmation for destructive operations (delete email, delete file, bulk send, etc.).
- **Policy:** Defined as a risk matrix in `safety_guard.py`. Do NOT weaken policies without explicit approval.
- **Output:** `SafetyDecision` (allow / block / require_confirmation)

### 6. Multi-Agent Orchestrator
- **File:** `gws_assistant/agent_system.py`
- **Role:** Top-level orchestrator. Wires Planner → Executor → Verifier. Handles session state, memory injection, and interface-specific response formatting.
- **Entry point for all interfaces** (CLI, GUI, Telegram, Web, REST)

---

## Tool System

### Service Catalog
- **File:** `gws_assistant/service_catalog.py`
- **Contains:** 60+ tool definitions for Gmail, Drive, Calendar, Docs, Sheets, Slides, Meet, Chat
- **Format:** Each tool has `name`, `description`, `parameters` (JSON Schema), and `required` fields
- **Rule for Jules:** When adding a new GWS capability, ALWAYS register it in `service_catalog.py` first. The Planner will not use a tool that is not registered here.

### Tool Wrappers
- **Directory:** `gws_assistant/tools/`
- Each file wraps one GWS service (e.g., `gmail_tools.py`, `drive_tools.py`, `calendar_tools.py`)
- Tools call `gws_runner.py` which invokes the GWS binary via subprocess
- **Return type:** Always `ToolResult` (defined in `models.py`) — never return raw dicts

### GWS Runner
- **File:** `gws_assistant/gws_runner.py`
- **Role:** Subprocess wrapper around the GWS binary (path set via `GWS_BINARY_PATH` env var)
- **CI mode:** When `CI=true`, binary path is set to `os.devnull` sentinel. The `is_file()` validation is skipped in CI mode. Do NOT remove this CI bypass.

---

## Configuration

### AppConfig
- **File:** `gws_assistant/config.py`
- **Class:** `AppConfig` — loaded via `AppConfig.from_env()`
- **Key env vars:**

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | ✅ | API key for LLM provider |
| `LLM_PROVIDER` | ✅ | Provider name (`openai`, `anthropic`, `openrouter`) |
| `LLM_MODEL` | ✅ | Primary model (must support tool-calling) |
| `LLM_FALLBACK_MODEL` | ❌ | First fallback model |
| `LLM_FALLBACK_MODEL2` | ❌ | Second fallback model |
| `GWS_BINARY_PATH` | ✅* | Path to GWS CLI binary (*not required in CI) |
| `DEFAULT_RECIPIENT_EMAIL` | ❌ | Default email for send actions |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |
| `CI` | auto | Set to `true` by pipeline — disables binary validation |

- **CI mode detection:** `ci_mode = _to_bool(os.getenv("CI"), default=False)`
- **Tool-model validation:** `validate_tool_model()` is called for all models. In CI, this validation is bypassed via `if not ci_mode`. Tests that need to test this validation path must use `monkeypatch.delenv("CI", raising=False)`.

### Model Registry
- **File:** `gws_assistant/model_registry.py`
- Maintains a list of known tool-capable models
- `validate_tool_model(model, label)` raises `ValueError` if model does not support tool-calling
- When adding new models, update `TOOL_CAPABLE_MODELS` list in this file

---

## Data Models

**File:** `gws_assistant/models.py`

| Model | Purpose |
|---|---|
| `Intent` | Parsed user intent with action, entities, and service |
| `PlanStep` | Single step in an execution plan (tool name + params) |
| `WorkflowState` | LangGraph state object passed between nodes |
| `ToolResult` | Standardized output from any tool execution |
| `VerificationResult` | Output of the verification engine |
| `SafetyDecision` | Output of the safety guard |
| `ConversationTurn` | Single turn in conversation history |

**Rule for Jules:** All inter-agent data MUST use these Pydantic models. Never pass raw dicts between agent layers.

---

## Testing

### Test Structure
```
tests/
├── test_unit_*.py           # Unit tests — fully mocked, no GWS binary needed
├── test_integration.py      # Integration tests — mocked GWS, real LangGraph workflow
├── test_hardening_policy.py # Security/hardening policy tests (config, safety guard)
├── test_live_integration.py # Live tests — requires real GWS binary + credentials
└── manual/                  # Manual test scripts (excluded from CI)
```

### Running Tests
```bash
# Unit tests only (CI safe)
pytest tests/ -m "not live_integration" --ignore=tests/manual --ignore=tests/test_live_integration.py

# Integration tests (mocked)
pytest tests/test_integration.py -m "not live_integration"

# Live integration (requires real GWS setup)
pytest tests/test_live_integration.py -m live_integration
```

### Key Test Rules for Jules
1. **Never modify test assertions** — fix the source code instead
2. **Never set `CI=true` inside tests** — use `monkeypatch.setenv` / `monkeypatch.delenv` for env control
3. **Tests that check non-CI validation** must unset CI: `monkeypatch.delenv("CI", raising=False)`
4. **Coverage thresholds:** unit tests ≥ 70%, integration tests ≥ 65% — do not lower these
5. **Markers:** tag live tests with `@pytest.mark.live_integration`

---

## CI/CD Pipeline

**File:** `.github/workflows/pipeline.yml`

### Job Order
```
lint → unit-tests → integration-tests → security
                                              ↓
                                       review-guard
                                              ↓ (if safe_to_merge)
                                        auto-merge
                                              ↓ (on failure)
                                      jules-auto-fix
```

### Auto-Merge Behavior
- Merges into **PR's actual base branch** (`github.event.pull_request.base.ref`) — NOT hardcoded `main`
- Squash merge with branch deletion
- Only triggers on `pull_request` events

### Review Guard
- Fetches all PR review threads via GraphQL
- **Blocks merge** if any thread is unresolved and non-outdated
- Tags `@google-labs-jules` on the linked Issue with exact unresolved comment details

### Jules Auto-Fix Loop
- Triggers on CI failure on any PR
- Posts `@google-labs-jules` on the linked Issue (or directly on PR if no Issue found)
- Includes full error logs, head branch, and target branch
- **Jules should push fixes to the head branch only — never merge manually**

### Environment Variables in CI
```yaml
CI: "true"           # Always set — disables GWS binary validation
PYTHONPATH: src      # Unit tests
PYTHONPATH: src:tests  # Integration tests
OPENAI_API_KEY: fake_key_for_testing   # Prevents config errors
LLM_API_KEY: fake_key_for_testing
```

---

## Jules-Specific Instructions

> Read this section carefully before making any changes.

### What Jules Can Freely Do
- Fix failing tests by correcting **source code** in `gws_assistant/`
- Add new tools by updating `service_catalog.py` + `gws_assistant/tools/`
- Update `models.py` to add new Pydantic fields
- Fix lint errors (ruff) and type errors (mypy)
- Add new test cases to existing test files
- Update `requirements.txt` for new dependencies

### What Jules Must NOT Do
- ❌ Modify test assertions or lower coverage thresholds
- ❌ Remove or weaken `safety_guard.py` policies
- ❌ Remove the CI mode bypass in `config.py` (`if not ci_mode`)
- ❌ Merge PRs manually — CI handles all merges via auto-merge
- ❌ Resolve review threads manually — fix the code and let CI re-check
- ❌ Add hardcoded credentials, API keys, or secrets anywhere in source
- ❌ Change the `GCP_PROJECT_ID`, `GCP_REGION`, or `GCP_SERVICE` values in pipeline.yml
- ❌ Add `main` or `master` hardcoded as merge targets — always use `base.ref`

### Branch Strategy
```
main          ← production (deploy triggers here)
develop       ← integration branch (most PRs target this)
feature/**    ← individual feature branches
hotfix/**     ← urgent fixes targeting main
```

### When CI Fails — Jules Checklist
1. Read the full error log posted in the Issue comment
2. Identify which job failed: `lint` / `unit-tests` / `integration-tests` / `security`
3. Fix source code in `gws_assistant/` — do NOT touch `tests/`
4. Run locally: `pytest tests/ -m "not live_integration" --ignore=tests/manual`
5. Push to the same head branch
6. Do not open a new PR — CI will auto-merge the existing one once green

### When Review Guard Blocks — Jules Checklist
1. Read each unresolved review comment linked in the Issue
2. Apply the suggested fix to the relevant file
3. Push to the same head branch
4. Do NOT manually resolve the review thread — the reviewer or CI will handle it

---

## Security Notes

- `safety_guard.py` must be consulted before any destructive GWS operation
- Never log full email bodies, file contents, or user PII
- `bandit`, `safety`, and `pip-audit` run on every PR — fix all HIGH severity findings
- Secrets are stored in GitHub Actions Secrets — never in `.env` files committed to the repo
- `.env.example` shows required keys but never contains real values

---

## Contacts

| Role | GitHub |
|---|---|
| Project Owner | [@haseeb-heaven](https://github.com/haseeb-heaven) |
| AI Fix Agent | [@google-labs-jules](https://github.com/google-labs-jules) |
| Code Review Bot | [@devin-ai-integration](https://github.com/apps/devin-ai-integration) |
| Security Review | [@coderabbitai](https://github.com/apps/coderabbit) |
