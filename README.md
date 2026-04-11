# Google Workspace Assistant

Smart CLI and GUI wrapper around `gws.exe` for Google Workspace automation.

The CLI uses CrewAI when an API key is configured, with a deterministic local fallback for simple requests. It can detect multiple Google Workspace services in one prompt, plan the execution order, run the matching `gws` commands, and format results for humans instead of dumping raw JSON.

## Supported Services

- Gmail
- Google Sheets
- Google Drive
- Google Calendar
- Google Docs
- Google Slides
- Google Contacts, via the Google People API surface exposed by `gws`

CrewAI's Google Workspace enterprise integration docs cover OAuth setup for Calendar, Gmail, Drive, Sheets, Slides, Docs, and Contacts: https://enterprise-docs.crewai.com/features/google-integrations

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
- Saves API keys if provided.
- Writes `.env`.

Setup is never triggered automatically. Normal app startup expects setup to already be complete.

## Run

Default CLI:

```bash
python cli.py
```

Backward-compatible launcher:

```bash
python gws_cli.py
```

GUI:

```bash
python gws_gui.py
```

Optional output capture:

```bash
python cli.py --save-output outputs/session.txt
```

## Example Request

```text
Find my tickets in Gmail and save to Sheets
```

The assistant plans this as:

1. Search Gmail for ticket-related messages.
2. Create a Google Sheet if no spreadsheet ID is supplied.
3. Append a readable summary of the Gmail results to the sheet.

If no Workspace service is detected, it returns:

```text
No Google Workspace service detected in your request.
```

## Project Structure

```text
.
|-- cli.py
|-- gws_cli.py
|-- gws_gui.py
|-- requirements.txt
|-- src/
|   `-- gws_assistant/
|       |-- agent_system.py
|       |-- cli_app.py
|       |-- config.py
|       |-- conversation.py
|       |-- execution.py
|       |-- gws_runner.py
|       |-- output_formatter.py
|       |-- planner.py
|       |-- service_catalog.py
|       `-- setup_wizard.py
`-- tests/
```

## Logs

Logs go to both console and `logs/gws_assistant.log` with rotation. The app logs setup state, agent planning decisions, actions, command execution, and errors.

## Tests

```bash
python -m pytest
```
