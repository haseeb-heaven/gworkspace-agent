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


