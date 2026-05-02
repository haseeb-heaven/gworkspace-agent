# Changelog

All notable changes to this project will be documented in this file.

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
