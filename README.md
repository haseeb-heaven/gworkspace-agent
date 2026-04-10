# Google Workspace Assistant (CLI + GUI)

Professional Python wrapper around `gws.exe` with:
- Natural-language request parsing using OpenAI SDK.
- OpenRouter or OpenAI provider selection via environment variables.
- Automatic service validation and clarification prompts.
- Two interfaces: Terminal UI (CLI) and desktop GUI.
- Structured logging to console and rotating log file.
- Unit-tested core planner, parser fallback, config, and command runner.

## Features

- Supported services: `drive`, `sheets`, `gmail`, `calendar`.
- If a user request does not include a supported service, the app asks again.
- If service is valid but action is missing, the app asks follow-up questions.
- Every command is validated, error-handled, and logged.
- Clean, modular architecture for easy extension.

## Project Structure

```text
.
├── gws_crud.py              # Backward-compatible CLI launcher
├── gws_cli.py               # CLI launcher
├── gws_gui.py               # GUI launcher
├── requirements.txt
├── .env.example
├── src/
│   └── gws_assistant/
│       ├── cli_app.py
│       ├── gui_app.py
│       ├── config.py
│       ├── conversation.py
│       ├── intent_parser.py
│       ├── planner.py
│       ├── gws_runner.py
│       └── logging_utils.py
└── tests/
```

## Setup

1. Create virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Copy env template and set your keys:

```bash
copy .env.example .env
```

3. Configure one provider:

- OpenAI:
  - `LLM_PROVIDER=openai`
  - `OPENAI_API_KEY=...`
- OpenRouter:
  - `LLM_PROVIDER=openrouter`
  - `OPENROUTER_API_KEY=...`

4. Ensure `gws.exe` exists, or set `GWS_BINARY_PATH` in `.env`.

## Run

CLI:

```bash
python gws_cli.py
```

GUI:

```bash
python gws_gui.py
```

Backward-compatible script:

```bash
python gws_crud.py
```

## Logs

- Console: rich formatted logs.
- File: `logs/gws_assistant.log` with rotation.

## Tests

```bash
pytest
```

## GitHub CI

GitHub Actions workflow runs tests automatically on push and pull request.

