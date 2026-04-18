# Robust Testing Architecture & Parallel Multi-Agent Framework

**Date:** 2026-04-18
**Status:** Draft
**Topic:** Implementation of a scalable, fault-tolerant testing architecture with parallel specialist agents and self-healing mechanisms.

## 1. Goal
Implement a production-grade testing and execution framework for the `gworkspace-agent`. This includes a centralized reliability layer (key rotation, strict configuration, triple-check verification) and a parallel multi-agent system to ensure 100% CRUD coverage across core Google Workspace services.

## 2. Architecture

### 2.1 Coordinator (Main Agent)
The Main Agent acts as the orchestrator and implementer of core infrastructure:
- **Centralized Credential Manager:** Enhances `GWSRunner` to support a pool of API keys/tokens from `.env`. Detects `429` errors, rotates keys, and applies exponential backoff.
- **Strict Configuration Enforcement:** Updates `AppConfig` and `models.py` to ensure `DEFAULT_RECIPIENT_EMAIL` and `GWS_BINARY_PATH` are derived strictly from environment variables.
- **Generic Verification Layer:** Implements `VerifierMixin` in `execution/verifier.py` to provide a "Triple-Check" protocol (3 re-fetches) for post-CRUD validation.
- **Orchestration Logic:** Handles the parallel dispatch of 7 specialist subagents and aggregates their progress via Telegram.

### 2.2 Specialist Subagents (Parallel)
Seven (7) Gemini CLI Subagents will be dispatched to handle the following services:
1. **Gmail**
2. **Drive**
3. **Sheets**
4. **Docs**
5. **Calendar**
6. **Tasks**
7. **Keep**

**Each Specialist Agent's Responsibilities:**
- **Audit:** Identify missing CRUD operations (Create, Read, Update, Delete) for their service.
- **Implement:** Add the execution logic to the respective service helper in `execution/`.
- **Test:** Write TDD tests (unit, manual, and validation) covering the full lifecycle (Create -> Verify -> Update -> Verify -> Delete).
- **Self-Heal:** Log fixes and root causes to Mem0 to build a persistent knowledge base.

## 3. Tech Stack
- **Python 3.11+**
- **Pytest:** With service-based markers and customized `pytest.ini`.
- **Gemini CLI Parallel Agents:** For concurrent implementation and testing.
- **Mem0:** For persistent learning and self-healing.
- **Telegram:** For real-time structured progress updates.

## 4. Workflows

### 4.1 GSD Ralph Loop (Service Agents)
1. **Plan:** Research existing service logic and tests.
2. **Execute:** Implement missing CRUD and verification steps.
3. **Validate:** Run `pytest` and confirm Triple-Check pass.
4. **Fix:** Debug failures and retry until green.
5. **Report:** Provide final CRUD coverage report to Coordinator.

### 4.2 Key Rotation Loop (Core)
1. Detect `429` or authentication error in `GWSRunner`.
2. Select next key from `.env` pool.
3. Wait (Exponential Backoff).
4. Retry request.

## 5. Success Criteria
- [ ] 100% CRUD coverage for all 7 core services.
- [ ] `pytest -v` runs Docs, Sheets, Email, Drive, Calendar, Tasks, and Keep tests by default.
- [ ] Zero hardcoded emails or OS-specific binary paths in the codebase.
- [ ] Real-time Telegram notifications for every major step.
- [ ] All bug fixes documented in Mem0 for persistent knowledge.
