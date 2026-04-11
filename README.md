# Google Workspace Agent - `langchain-ai`

This branch packages the assistant around a LangChain planner, a LangGraph workflow, and the `gws` Google Workspace CLI. It turns natural-language requests into multi-step workflows across Gmail, Drive, Docs, Sheets, Calendar, Chat, and Meet, with built-in web search and sandboxed Python execution.

## What This Branch Includes

- LangChain-based plan generation with a heuristic fallback when no model key is configured
- LangGraph workflow execution with retries and readable final reports
- Internal web search via DuckDuckGo with Tavily fallback
- Sandboxed Python code execution with `restricted_subprocess`, Docker, or E2B backends
- Google Workspace automations through the bundled `gws.exe`
- CLI and Gradio entrypoints

## Architecture

![System Architecture](assets/architecture_diagram.png)

Core modules:

- `src/gws_assistant/agent_system.py`: converts requests into ordered task plans
- `src/gws_assistant/langchain_agent.py`: structured LangChain planning
- `src/gws_assistant/langgraph_workflow.py`: workflow orchestration and retries
- `src/gws_assistant/execution.py`: task execution and context passing between steps
- `src/gws_assistant/tools/web_search.py`: web search and lightweight result summarization
- `src/gws_assistant/tools/code_execution.py`: sandboxed code interpreter support

## Setup

1. Activate your environment:

```powershell
& D:\Code\MuslimGuideAI\pyenv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Create your env file if needed:

```powershell
Copy-Item .env.example .env
```

4. Run the interactive setup wizard:

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

Force heuristic mode:

```powershell
python .\gws_cli.py --no-langchain --task "Search Drive for quarterly planning docs"
```

Launch Gradio:

```powershell
python .\gws_gradio.py
```

## Example Workflows

Research + Docs + Sheets + Gmail:

```text
Find top 3 Agentic AI frameworks, save the data to Google Docs and Google Sheets, and send an email to haseebmir.hm@gmail.com
```

Direct code execution:

```text
Run code: print(sum(i * i for i in range(10)))
```

If you need to use the interpreter in a stronger sandbox, switch `CODE_EXECUTION_BACKEND` to `docker` or `e2b`.

## Testing

Run the full suite:

```powershell
python -m pytest
```

Helpful smoke checks:

```powershell
python .\gws_cli.py --help
python .\gws_gradio.py --help
```

## Notes

- Web search is used for external research tasks before writing into Docs or Sheets.
- Email workflows can automatically include generated Docs and Sheets links in the message body.
- The branch is designed to work even without an LLM key, but LangChain planning gives better multi-step plans.

## License

MIT
