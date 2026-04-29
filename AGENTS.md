# AGENTS.md

This file provides AI coding agents with the context, conventions, and constraints needed to work effectively in this repository. It complements the README by covering build steps, test commands, code style, and project-specific rules that are most useful to an automated contributor.

Compatible with: OpenAI Codex, GitHub Copilot Agent, Google Jules, Devin, Cursor, Windsurf, Aider, Goose, Factory, Zed, Warp, and any agent that reads AGENTS.md.

---

## Project Overview

**GWorkspace Agent** is a LangGraph-powered AI assistant for Google Workspace. It accepts natural language commands and translates them into Google Workspace API calls (Gmail, Drive, Calendar, Docs, Sheets, Slides, Meet, Chat) using a multi-agent planning and execution pipeline.

- **Language:** Python 3.11
- **Core Framework:** LangGraph + LangChain
- **LLM Backend:** OpenAI-compatible API (configurable via `LLM_PROVIDER` / `LLM_MODEL`)
- **Interfaces:** CLI, Desktop GUI (Tkinter), Web UI (Gradio), Telegram Bot, Cloud Run (REST)
- **Deployment:** Google Cloud Run via Docker
- **Package root:** `gws_assistant/`

---

## Dev Environment Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install all dependencies
pip install -r requirements.txt
pip install -e .
pip install ruff mypy pytest pytest-cov

# 3. Copy environment config
cp .env.example .env
# Fill in LLM_API_KEY, LLM_PROVIDER, LLM_MODEL, and GWS_BINARY_PATH

# 4. Run setup wizard (first time only)
python -m gws_assistant --setup
```

### Required Environment Variables

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | ✅ | API key for LLM provider |
| `LLM_PROVIDER` | ✅ | `openai`, `anthropic`, or `openrouter` |
| `LLM_MODEL` | ✅ | Primary model — must support tool-calling |
| `LLM_FALLBACK_MODEL` | ❌ | First fallback model |
| `LLM_FALLBACK_MODEL2` | ❌ | Second fallback model |
| `GWS_BINARY_PATH` | ✅* | Path to GWS CLI binary (*skipped in CI) |
| `DEFAULT_RECIPIENT_EMAIL` | ❌ | Default email for send operations |
| `LOG_LEVEL` | ❌ | Logging verbosity (default: `INFO`) |
| `CI` | auto | Set by pipeline — disables binary path validation |

---

## Build & Run Commands

```bash
# CLI interface
python gws_cli.py

# Desktop GUI
python gws_gui.py

# Web UI (Gradio)
python gws_gui_web.py

# Telegram Bot
python gws_telegram.py

# Docker (production)
docker build -t gworkspace-agent . && docker run --env-file .env gworkspace-agent
```

---

## Testing Instructions

The CI plan lives in `.github/workflows/pipeline.yml`. All checks must pass before a PR is merged.

```bash
# Run unit tests (safe for CI — no GWS binary needed)
pytest tests/ \
  -m "not live_integration" \
  --ignore=tests/manual \
  --ignore=tests/test_live_integration.py \
  --cov=src --cov=gws_assistant \
  --cov-fail-under=70 \
  -v

# Run integration tests (mocked GWS)
pytest tests/test_integration.py \
  -m "not live_integration" \
  --cov=gws_assistant.langgraph_workflow \
  --cov=gws_assistant.execution \
  --cov-fail-under=65 \
  -v

# Run live integration tests (requires real GWS binary + credentials)
pytest tests/test_live_integration.py -m live_integration -v
```

### Test Structure

```
tests/
├── test_unit_*.py           # Unit tests — fully mocked, no GWS binary needed
├── test_integration.py      # Integration tests — mocked GWS, real LangGraph workflow
├── test_hardening_policy.py # Security/hardening policy tests
├── test_live_integration.py # Live tests — requires real credentials
└── manual/                  # Manual scripts — excluded from CI
```

### Testing Conventions

- Fix failing tests by correcting **source code**, never by modifying test assertions
- Coverage thresholds are enforced: unit ≥ 70%, integration ≥ 65% — do not lower them
- Tag live tests with `@pytest.mark.live_integration`
- Do not hardcode `CI=true` inside tests; use `monkeypatch.setenv` / `monkeypatch.delenv`
- Tests that exercise non-CI validation must explicitly unset CI: `monkeypatch.delenv("CI", raising=False)`
- Add or update tests for every code change, even if not requested

---

## Code Style Guidelines

```bash
# Lint (must pass with zero errors)
ruff check .

# Type check
mypy src --ignore-missing-imports

# Auto-fix safe lint issues
ruff check . --fix
```

- Follow PEP 8 with a 100-character line limit
- All public functions and classes must have docstrings
- Use type annotations on all function signatures
- Inter-agent data must use Pydantic models from `models.py` — never pass raw `dict` between layers
- Return type from any tool wrapper must be `ToolResult` (defined in `models.py`)

---

## Repository Structure

```
gworkspace-agent/
├── gws_assistant/               # Core package
│   ├── agent_system.py          # Multi-agent orchestrator (Planner → Executor → Verifier)
│   ├── planner.py               # Decomposes user intent into ordered PlanSteps
│   ├── intent_parser.py         # NLU — parses raw input into structured Intent objects
│   ├── langgraph_workflow.py    # LangGraph state machine — primary execution workflow
│   ├── langchain_agent.py       # LangChain ReAct agent — alternative backend
│   ├── service_catalog.py       # Registry of 60+ GWS tool definitions
│   ├── verification_engine.py   # Validates tool outputs against original intent
│   ├── safety_guard.py          # Blocks destructive/irreversible GWS operations
│   ├── execution/               # Runs GWS binary tool calls
│   ├── tools/                   # Per-service tool wrappers (Gmail, Drive, Calendar …)
│   ├── llm_client.py            # LLM abstraction — OpenAI / Anthropic / OpenRouter
│   ├── config.py                # AppConfig — loads and validates all env vars
│   ├── model_registry.py        # Tool-capable model registry + fallback chain
│   ├── memory.py                # Short-term conversation memory
│   ├── memory_backend.py        # Long-term persistent memory backend
│   ├── models.py                # Pydantic models: Intent, PlanStep, WorkflowState, ToolResult …
│   ├── output_formatter.py      # Formats responses per interface (CLI / GUI / API)
│   ├── relevance.py             # Relevance scoring — filters tool results by intent
│   ├── drive_query_builder.py   # Builds Drive API query strings
│   ├── gmail_query_builder.py   # Builds Gmail search query strings
│   ├── exceptions.py            # Custom exception hierarchy
│   ├── logging_utils.py         # Structured logging setup
│   ├── cli_app.py               # CLI interface
│   ├── gui_app.py               # Desktop GUI (Tkinter)
│   ├── gradio_app.py            # Web UI (Gradio)
│   ├── telegram_app.py          # Telegram Bot
│   ├── gws_runner.py            # Subprocess wrapper for GWS CLI binary
│   ├── setup_wizard.py          # First-run setup wizard
│   └── chat_utils.py            # Shared chat utilities
├── gws_cli.py / gws_gui.py / gws_gui_web.py / gws_telegram.py   # Entrypoints
├── tests/                       # All tests
├── framework/                   # Internal framework utilities
├── scripts/                     # Setup and utility scripts
├── .github/workflows/pipeline.yml  # CI/CD pipeline
├── Dockerfile / Dockerfile.sandbox
├── requirements.txt
└── pyproject.toml
```

---

## Architecture: Core Components

### Planner (`planner.py`)
Receives a parsed `Intent` and returns an ordered `List[PlanStep]`. Each step maps exactly to a tool registered in `service_catalog.py`. Do not reference tool names that are not in the catalog.

### Executor — LangGraph Workflow (`langgraph_workflow.py`)
State machine with nodes: `parse_intent → plan → execute_step → verify → respond`. Uses `llm_client.py` with automatic fallback via `model_registry.py`.

### Executor — LangChain ReAct (`langchain_agent.py`)
Alternative backend activated when `USE_LANGCHAIN=true`. Dynamically loads tools from `gws_assistant/tools/` and integrates `memory.py`.

### Verification Engine (`verification_engine.py`)
Post-execution validator. Input: `Intent + List[ToolResult]`. Output: `VerificationResult` (passed / failed / needs_retry). Triggers re-planning on failure.

### Safety Guard (`safety_guard.py`)
Pre-execution safety layer. Must be consulted before any destructive GWS operation. Outputs `SafetyDecision` (allow / block / require_confirmation). The risk policy matrix must not be weakened without explicit project owner approval.

### Service Catalog (`service_catalog.py`)
Registers all 60+ GWS tools with `name`, `description`, `parameters` (JSON Schema), and `required` fields. **When adding a new GWS capability, register it here first.** The Planner will not use an unregistered tool.

### GWS Runner (`gws_runner.py`)
Subprocess wrapper for the GWS CLI binary. Binary path comes from `GWS_BINARY_PATH`. When `CI=true`, the `is_file()` check is skipped — this bypass is required for CI and must not be removed.

---

## CI/CD Pipeline

**File:** `.github/workflows/pipeline.yml`

### Job Execution Order

```
lint → unit-tests → integration-tests → security
                                              ↓
                                       review-guard
                                    (blocks on unresolved
                                      review threads)
                                              ↓ safe_to_merge == true
                                         auto-merge
                                              ↓ on any failure
                                        ci-auto-fix
```

### Auto-Merge
- Squash-merges into the **PR’s actual base branch** (`github.event.pull_request.base.ref`)
- Branch is deleted after merge
- Do not hardcode `main` or `master` as a merge target anywhere in the pipeline

### Review Guard
- Queries all review threads via GraphQL
- Blocks merge if any thread is unresolved and non-outdated
- Posts detailed unresolved comment context to the linked Issue

### CI Failure Auto-Fix
- Triggers on any job failure in a PR
- Posts full error logs and instructions to the linked Issue (or PR if no Issue found)
- **Agent must push fixes to the same head branch — never open a new PR or merge manually**

---

## PR & Commit Instructions

- **Commit format:** `<type>(<scope>): <short description>` — e.g. `fix(planner): handle empty intent`, `feat(tools): add Sheets append tool`
- **PR title:** mirror the primary commit message
- **Branch naming:**
  - `feature/<short-description>` for new features
  - `fix/<short-description>` for bug fixes
  - `hotfix/<short-description>` for urgent production fixes
- Always run `ruff check .` and the unit test suite before pushing
- Do not open a new PR to fix a failing one — push to the existing branch; CI will auto-merge once green
- Do not merge manually — CI handles all merges

---

## What an Agent Can Do

- Fix failing tests by correcting source code in `gws_assistant/`
- Add new GWS tools by updating `service_catalog.py` and adding a wrapper in `gws_assistant/tools/`
- Update `models.py` to add or extend Pydantic models
- Fix lint (`ruff`) and type (`mypy`) errors
- Add new test cases to existing test files
- Update `requirements.txt` for new dependencies
- Refactor modules within `gws_assistant/` following existing patterns
- Improve docstrings and inline comments
- Update this file (`AGENTS.md`) when architecture or conventions change

---

## What an Agent Must Not Do

- Modify test assertions or lower coverage thresholds
- Remove or weaken `safety_guard.py` risk policies
- Remove the CI mode bypass in `config.py` (`if not ci_mode`)
- Merge PRs manually — CI manages all merges
- Resolve review threads manually — fix the code and let CI re-verify
- Add hardcoded credentials, API keys, or secrets in source files
- Change `GCP_PROJECT_ID`, `GCP_REGION`, or `GCP_SERVICE` in pipeline.yml
- Hardcode `main` or `master` as a merge target — always use `base.ref`
- Pass raw `dict` objects between agent layers — use Pydantic models

---

## Security Considerations

- Never log full email bodies, file contents, or user PII
- `bandit`, `safety`, and `pip-audit` run on every PR — fix all HIGH severity findings before pushing
- Secrets live in GitHub Actions Secrets only — never in committed `.env` files
- `.env.example` documents required keys but contains no real values
- The `safety_guard.py` policy matrix is the authoritative source for what operations are allowed without user confirmation

---

## Branch Strategy

```
main        ← production branch (Cloud Run deploy triggers on push)
develop     ← integration branch (most PRs target this)
feature/**  ← feature development
hotfix/**   ← urgent production fixes
```
