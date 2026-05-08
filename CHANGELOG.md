## [v1.0.1] - 2026-05-05
### Added/Changed/Fixed
- Add STATS.md with repository statistics in table format and reference in README
- Update pre-push hook to only check for Python files
- Update pre-push hook to run unit tests only on code changes
- Add Star History section to README
- updated test verification engine
- updated pre-commit for unit-test run
- Pre-commit on Unit test
- Fix failing manual integration tests
- Fix tmp_path fixture issue and add missing pytest markers
- Remove gws_only markers from manual tests and revert shared.py changes
- Update calendar CRUD tests with real event ID from user's calendar
- Add chat and meet markers to pytest.ini and update calendar test with event ID
- Add comprehensive CRUD tests for all Google Workspace services
- Add service markers to gws_binary tests and filtering logic
- Add tests for all remaining gws.exe services
- Add unit tests for direct gws.exe binary commands
- added 5 step verification to all manual tests
- updated files
- Fully ignore scratch folder
- updated test integration
- updated test integration
- updated requirements
- updated security to ENV scanning precommit
- updated Agents.md file
- fix(verification): downgrade empty values error to WARNING for sheets append
- fix(execution): sanitize [File: ...] patterns in code results before sheets append
- fix(workflow): chain of fixes for drive-to-sheets-to-email task
- fix(models): skip stub validation for drive.export_file file_id
- fix(verification): allow placeholders in params, block only in results
- fix(verification): only block unresolved placeholders in result data, not params
- Merge remote-tracking branch 'origin/develop' into cascade/implement-multi-user-credential-upload-6fa976
- feat(gradio): add multi-user OAuth authentication flow
- Cascade snapshot 2026-05-04T03:35:50.3272082Z
- chore(deps): bump actions/upload-artifact from 4 to 7 (#91)
- chore(deps): bump actions/download-artifact from 4 to 8 (#92)
- chore(deps): bump google-github-actions/deploy-cloudrun from 2 to 3 (#93)
- chore(deps): bump google-github-actions/auth from 2 to 3 (#94)
- chore(deps): bump google-github-actions/setup-gcloud from 2 to 3 (#95)
- chore(deps): update ddgs requirement from >=9.13.0 to >=9.14.2 (#96)
- chore(deps): update python-telegram-bot requirement (#97)
- Merge pull request #98 from haseeb-heaven/dependabot/docker/python-3.14-slim
- Merge remote-tracking branch 'origin/develop' into dependabot/docker/python-3.14-slim
- Merge branch 'develop' of https://github.com/haseeb-heaven/gworkspace-agent into develop
- chore(deps): bump python from 3.11-slim to 3.14-slim
- Configure Dependabot for multiple ecosystems
- Create dependabot.yml for version updates
- Merge branch 'develop' into master
- updated gitignore file
- updated gitignore
- fix(agent): prevent DoS via regex backtracking in heuristic computation
- fix(verification): always detect unresolved placeholders regardless of path validation
- chore(release): rename tags to 0.1.0-0.5.0 and update changelog
- chore(release): add changelog entries for v0.0.6 to v0.0.10
- docs: update changelog history and add release reference to README

## [v1.0.0] - 2026-05-04

### Major Release - Production Ready

This is the first stable production release of Google Workspace Agent. This milestone represents a complete, feature-rich AI assistant for Google Workspace with comprehensive safety, verification, and multi-service orchestration capabilities.

### Added
- **Complete Multi-Agent System**: Full LangGraph-powered agent system with Planner, Executor, and Verifier nodes
- **5-Step Verification Engine**: Strict, non-bypassable verification system with CRITICAL, ERROR, and WARNING severity levels
- **Hybrid ReAct + LangGraph Architecture**: LLM-driven planner generates typed DAG of tasks with stateful execution
- **Multi-Service Orchestration**: Chain Gmail, Drive, Sheets, Docs, Calendar, and Code execution in single natural language request
- **Long-Term Memory via Mem0**: Agent learns from past interactions and recalls user preferences across sessions
- **Sandboxed Code Execution**: Python code runs in restricted E2B sandbox with stdout/stderr capture
- **Safety-by-Default**: Read-Only mode blocks writes; Sandbox mode requires manual confirmation for state changes
- **Multi-Interface Support**: CLI, Desktop GUI (Tkinter), Web UI (Gradio), and Telegram Bot
- **Model Agnostic Design**: Works with any OpenAI-spec tool-calling model via OpenRouter or direct APIs
- **20+ Google Services**: Support for Gmail, Drive, Sheets, Docs, Calendar, Slides, Contacts, Chat, Tasks, Keep, Forms, Meet, Classroom, Admin SDK, Apps Script, and more
- **100+ Tool Actions**: Comprehensive service catalog with detailed parameter validation
- **Heuristic Planning**: Fallback planning system for common patterns (calendar-to-email, drive folder upload, etc.)
- **Recursive Placeholder Resolution**: Advanced context variable substitution with nested field access
- **Drive File Operations**: Upload, download, export, move, rename, delete, share with MIME type detection
- **Gmail Attachment Support**: Attach Drive files and export Docs to PDF before emailing
- **Web Search Integration**: Tavily-powered web search with fallback to DuckDuckGo
- **CI/CD Pipeline**: Complete GitHub Actions workflow with auto-merge, review guard, and security scanning
- **Comprehensive Test Suite**: Unit tests, integration tests, and live integration tests with 70%+ coverage

### Fixed
- All placeholder resolution bugs including nested field access, bracket-index, and sender variants
- Drive query sanitization to prevent 400 Invalid Value errors
- Gmail attachment handling with proper Drive file export to PDF
- OpenRouter 429 rate-limit handling with exponential backoff and model fallback
- LangChain structured output schema errors
- Sandbox import issues and structured output None handling
- CLI --help hanging on stdin input
- SpreadsheetId reference resolution in Sheets operations
- Docs empty text handling
- Wildcard sender row processing in Gmail
- Step-output placeholder binding
- Web search extraction issues
- Missing gmail.send in tool catalog
- Admin service stub to prevent crashes
- Code stdout appearing in sheet values
- Wrong to_email from receipt sender
- Empty second tab in Sheets operations
- And 200+ additional bug fixes across all components

### Changed
- Enhanced verification engine with stricter 5-check system
- Improved context updater with better debug logging
- Enhanced calendar-to-email workflow with placeholder resolution
- Improved test coverage for verification engine (70%+ unit, 65%+ integration)
- Refactored planner/executor contract for stability
- Enhanced error taxonomy and reflection loop
- Improved Drive API query string sanitization
- Enhanced service catalog with rich tool descriptions
- Improved model registry with fallback chain support
- Enhanced safety guard with destructive operation protection
- Improved CI/CD with review guard and auto-merge
- Enhanced documentation with comprehensive setup guide

### Security
- Restricted Python sandbox for code execution
- Safety guard for destructive operations
- Enhanced path validation and input sanitization
- 5-step verification engine that cannot be bypassed
- Pre-execution verification to prevent destructive operations
- Bulk operation protection requiring confirmation
- Email recipient enforcement via security policy
- Scope validation framework for OAuth permissions
- Data corruption detection with truncation markers
- Referential integrity checks for parent/child relationships

### Breaking Changes
- Minimum Python version raised to 3.10
- Some environment variable names changed for consistency
- Verification engine is now strict by default (can be configured via env vars)

---

## [v0.9.4] - 2026-05-04
### Added/Changed/Fixed
- updated git cache

## [v0.9.3] - 2026-05-04
### Added/Changed/Fixed


## [v0.9.2] - 2026-05-04
### Added/Changed/Fixed


## [v0.9.1] - 2026-05-04
### Added/Changed/Fixed
- fix(tests): resolve unit/integration test failures after verification hardening
- fix(verification): resolve manual test failures after hardening
- chore(scripts): add enhanced release scripts to repository
- chore(scripts): enhance release scripts to update all version files

# Changelog

All notable changes to this project will be documented in this file.

## [0.9.0] - 2026-05-04

### Added
- DriveFolderUploadStrategy heuristic for folder+upload requests
- Calendar multi-step heuristic strategies
- CalendarToEmailStrategy for cross-service calendar->email operations
- TasksFindDeleteStrategy for multi-step task deletion
- TasksFindAndUpdateStrategy and tasks context tracking
- DRIVE_FOLDER_NAME variable to environment files

### Fixed
- Harden invalid data and attachment checks in verification
- Handle empty drive file lists by setting fallback context values
- Detect drive file lists without task service check
- Resolve calendar events placeholder and add context tracking
- Handle drive.list_files with direct list response format
- Halt on unresolved placeholders in email body
- Skip CHECK 5 idempotency check for slides operations
- Add form output formatter to display form title
- Make heuristic code execution compute arithmetic expressions instead of placeholder
- Narrow Gmail validation to exclude chat send_message
- Improve calendar action detection in heuristic planner
- Pass q parameter in calendar list_events command
- Catch ValidationError and refine save regex
- Address multiple review comments and test assertion fixes
- Fix Drive ID validation, TypedDict safety, and delete-by-name strategy
- Sync pyproject.toml to v0.8.0 to match README and CHANGELOG

### Changed
- Enhanced verification engine with stricter checks
- Improved context updater with better debug logging
- Enhanced calendar-to-email workflow with placeholder resolution
- Improved test coverage for verification engine

---

## [0.8.0] - 2026-05-03

### Added
- **5-Step Verification Engine** - Strict, non-bypassable verification system with severity levels (CRITICAL, ERROR, WARNING)
  - CHECK 1: Parameter Validation - validates input parameters for correctness and completeness
  - CHECK 2: Permission & Scope Validation - verifies operation is within allowed scopes and user permissions
  - CHECK 3: Result Validation - validates operation result structure and success status
  - CHECK 4: Data Integrity & Consistency Validation - verifies data consistency across operations
  - CHECK 5: Idempotency & Safety Validation - validates operation safety and retry safety
- VerificationSeverity enum with CRITICAL, ERROR, and WARNING levels
- Enhanced VerificationError class with check_number and severity parameters
- Pre-execution verification to catch issues before operations run
- Bulk operation protection requiring `_bulk_confirmed=true` for operations affecting >10 items
- Destructive operation protection requiring `_safety_confirmed=true` for dangerous operations
- Configurable verification behavior via environment variables
- Safety guard integration for destructive operations
- Email recipient enforcement via security policy
- Scope validation framework for OAuth permissions
- Data corruption detection with truncation markers
- Referential integrity checks for parent/child relationships
- Word-boundary regex matching for bulk keyword detection (prevents false positives)
- Backward compatibility with validation tests

### Fixed
- Bandit B101 security warnings in test files by adding # nosec B101 comments
- Type annotation issues in agent_system.py and safety_guard.py
- Missing import re in executor.py
- Backward compatibility issues with validation tests
- Check ordering issue where destructive check ran before bulk check
- False positive bulk detection from "all" keyword in verification_bulk_indicators

### Changed
- VerificationEngine.verify() now runs all 5 checks in sequence with proper logging
- Enhanced verification engine with configurable severity-based error handling
- Improved error messages with check numbers and severity levels
- Bulk confirmation implicitly satisfies destructive confirmation for operations that are both
- Removed "all" from default verification_bulk_indicators to prevent false positives on common English words

### Security
- Enhanced verification engine with strict 5-check system that cannot be bypassed
- Pre-execution verification to prevent destructive operations from running before validation
- Improved bulk operation detection with word-boundary regex matching
- Enhanced scope validation for OAuth permissions
- Data corruption detection mechanisms

---

## [0.7.0] - 2026-05-02

### Added
- Comprehensive file type support with MIME type detection for uploads, exports, and downloads
- File types module with support for Google Workspace, Office, OpenDocument, images, audio, video, archives, and code files
- Drive file operations: upload, copy, move, rename, update metadata, delete, and trash
- Enhanced export format negotiation for Google Workspace native files (Docs, Sheets, Slides, Drawings)
- Binary media detection and handling for images, audio, video, and PDF files
- Integration tests for all file types and Drive lifecycle operations
- Live integration tests for end-to-end file operations
- Agent planning system with heuristic fallback and LLM-based planning
- Semantic memory backend for conversation context
- Restricted Python code execution sandbox for security
- Triple verification engine for automated resource validation
- Service catalog with 60+ Google Workspace tool definitions
- Safety guard system for destructive operations
- LLM client with automatic API key rotation and fallback
- LangGraph-based execution workflow
- CI/CD pipeline with comprehensive testing and security scanning
- Custom PR/MR automation skills

### Fixed
- Web search query extraction to properly truncate at chaining clauses
- Document title extraction to handle "call that" syntax
- Drive → Sheets → Gmail workflow to export actual document content
- Image attachment handling in Drive → Email workflow (uses Drive links instead of binary export)
- Sorting logic for code execution with proper numeric sorting
- Email detection to avoid false positives from search topics
- Web search routing to prevent Gmail list_messages for web search prompts
- Placeholder resolution for Gmail body parameter
- Pattern ordering to prioritize Drive-based requests over Gmail
- Sheet guards to prevent incorrect metadata pattern matching
- Idempotency cache side effects in executor
- Gmail verification in tests
- Telegram race conditions
- Path traversal vulnerabilities in planner
- JSON parsing errors in executor
- Argument validation across multiple components

### Changed
- Improved heuristic pattern matching and service detection
- Enhanced verification engine with better resource validation
- Refactored fake Google Workspace test double for comprehensive file operation mocking
- Consolidated security workflows in CI/CD pipeline
- Improved error messages and logging throughout the system

### Security
- Added Restricted Python sandbox for code execution
- Implemented safety guard for destructive operations
- Enhanced path validation and input sanitization
- Consolidated Snyk security scanning

---

## [0.6.1] - Previous Release

### Added
- Initial Google Workspace assistant functionality
- Basic Drive, Gmail, Calendar, and Sheets integration
- CLI and GUI interfaces
