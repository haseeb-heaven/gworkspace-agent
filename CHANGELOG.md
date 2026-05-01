# Changelog

All notable changes to this project will be documented in this file.

## [v0.6.1] - 2026-04-30
### Fixed
- Fixed `WorkflowNodes.plan_node` calling `self._append_history` instead of module-level `_append_history`
- Fixed `WorkflowNodes.format_output_node` returning hardcoded placeholder instead of using `self.formatter`
- Fixed API key rotation loop retrying same key for non-OpenRouter models in `call_llm`
- Pinned Snyk GitHub Action to `v1.0.0` instead of mutable `@master` ref

## [0.6.0] - 2026-04-30
### Added
- Implemented comprehensive unit and manual integration test suites.
- Enhanced core agent functionality across CLI, GUI, and Web interfaces.

## [1.5.0] - Sandbox and Workspace Safety
### Added
- **Sandbox Mode**: Implemented an interactive mode to intercept destructive actions (delete, write) and prompt for confirmation.
- **Read-Only Mode**: Added failsafe defaults that block state-changing workspace operations.
- **CLI Options**: Added `--sandbox` / `--no-sandbox` and `--read-only` / `--read-write` override flags.
### Changed
- Rewrote the README with comprehensive setup instructions, interface documentation, and troubleshooting guides.
### Fixed
- Refined task generation and strict service detection.
- Fixed code execution context updates and 6 execution bugs in resolver and executor.
- Fixed bugs in `planner.py` regarding command argument mapping.

## [1.4.0] - Telegram Bot Optimization & Agent Orchestration
### Added
- Implemented `WorkspaceAgentSystem` for natural-language request planning using LLMs with a heuristic fallback.
- Added infinite timeout for GWS tasks executed via Telegram to handle complex API operations.
### Changed
- Finalized Telegram bot stability, including API key rotation and direct chat fallback retries.
- Secured unit tests by excluding `live_integration` tests by default.
### Fixed
- Resolved merge conflicts and orchestrated complex branch integrations (PR #6, #8, #10).
- Removed hardcoded email redirection, delegating it to central security policy.

## [1.3.0] - Verification Engine & Semantic Memory
### Added
- **VerificationEngine**: Introduced a post-execution and pre-execution data integrity validator to ensure correct API payloads.
- **Long-Term Memory**: Implemented a multi-layered local JSONL-based memory system.
- Added self-hosted Mem0 instances support via `MEM0_HOST`.
### Changed
- Applied comprehensive `ruff` linting across the codebase.
- Added end-to-end integration tests for end-to-end Google Workspace Agent flows.
### Fixed
- Fixed Mem0 `user_id` filters and resolved search redundancies.
- Addressed missing dependencies (`portalocker`) and `read_mem0` failures.

## [1.2.0] - Core Framework & Service Coverage
### Added
- Built the core agent framework with modular execution, batch task processing, and robust shared data models (`AppConfigModel`, `ExecutionResult`).
- Finalized 100% CRUD test coverage for 7 core Workspace services (Gmail, Drive, Sheets, Docs, Calendar, Keep, Tasks).
- Implemented OpenRouter API key rotation and rate-limit handling across LLM layers.
### Changed
- Refactored `execution.py` into a modular package (`execution/` directory) and enforced dynamic configuration.
- Established a structured test framework with dynamic `pytest` service-based markers.
### Fixed
- Fixed bug causing `slots=True` configuration dropping mutations by renaming `_current_key_idx`.
- Pre-compiled frequently used regex patterns in the execution engine to improve performance.

## [1.1.0] - Initial LangGraph Architecture & Intent Parsing
### Added
- **LangGraph Workflow**: Initialized DAG-based workflow for assistant task planning, execution, and reflection.
- **IntentParser**: Added LLM-based extraction with a heuristic fallback for generating plans offline.
- Added GWS subprocess runner (`GWSRunner`) with CLI argument size handling and backoff retries.
- Implemented drive export file resolution, folder validation, and Drive-to-Gmail heuristic flows.
### Changed
- Hardened agentic email enforcement and sanitized heuristic planning with strict recipient overrides.
### Fixed
- Refined heuristic service detection and improved code execution output visibility.
- Prevented replan loops by improving parameter extraction and heuristic code generation.
