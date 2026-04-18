# Robust Testing Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a production-grade testing architecture with key rotation, triple-check verification, and parallel specialist agents for full GWS CRUD coverage.

**Architecture:** Use a Mixin-based approach for the core `PlanExecutor` and a centralized `CredentialManager` in `GWSRunner` to handle rate limits and rotation. Dispatch service specialists in parallel for CRUD implementation.

**Tech Stack:** Python 3.11, Pytest, Gemini CLI Subagents, Mem0, Telegram.

---

### Task 1: Core Reliability - Strict Config & Security

**Files:**
- Modify: `src/gws_assistant/config.py`
- Modify: `src/gws_assistant/models.py`
- Modify: `pytest.ini`

- [ ] **Step 1: Enforce strict dynamic configuration**
Modify `src/gws_assistant/config.py` to remove any hardcoded fallbacks for binary paths and emails.
```python
# src/gws_assistant/config.py
default_recipient_email = os.getenv("DEFAULT_RECIPIENT_EMAIL")
if not default_recipient_email:
    raise ValueError("DEFAULT_RECIPIENT_EMAIL must be set in .env")
```

- [ ] **Step 2: Update Pytest defaults**
Modify `pytest.ini` to enable all core services by default.
```ini
addopts = -v -m "not manual and (gmail or docs or sheets or drive or calendar or tasks or keep)"
```

- [ ] **Step 3: Verify config loading**
Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add src/gws_assistant/config.py src/gws_assistant/models.py pytest.ini
git commit -m "feat: enforce strict dynamic configuration and update pytest defaults"
```

---

### Task 2: Core Reliability - Key Rotation & Rate-Limit Handling

**Files:**
- Modify: `src/gws_assistant/gws_runner.py`

- [ ] **Step 1: Implement Credential Rotation in GWSRunner**
Add logic to `GWSRunner.run` to detect 429 errors and rotate keys from a list in `.env`.
```python
def _rotate_key(self):
    keys = os.getenv("OPENROUTER_API_KEY", "").split(",")
    self.current_key_index = (self.current_key_index + 1) % len(keys)
    os.environ["OPENROUTER_API_KEY"] = keys[self.current_key_index]
```

- [ ] **Step 2: Add exponential backoff**
Implement retry logic with exponential backoff for rate-limited requests.

- [ ] **Step 3: Write test for rotation**
Create `tests/test_key_rotation.py` mocking a 429 response then a 200 after rotation.

- [ ] **Step 4: Run test**
Run: `pytest tests/test_key_rotation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add src/gws_assistant/gws_runner.py tests/test_key_rotation.py
git commit -m "feat: implement API key rotation and rate-limit handling"
```

---

### Task 3: Core Reliability - Triple-Check Verifier

**Files:**
- Modify: `src/gws_assistant/execution/verifier.py`
- Modify: `src/gws_assistant/execution/executor.py`

- [ ] **Step 1: Implement Triple-Check logic**
Update `VerifierMixin` in `src/gws_assistant/execution/verifier.py` to perform 3 re-fetches.
```python
def verify_resource(self, service, resource_id):
    for i in range(3):
        time.sleep(2 * i) # Increasing delay
        result = self.runner.run([service, "get", resource_id])
        if not result.success: return False
    return True
```

- [ ] **Step 2: Integrate into execute_single_task**
Ensure `PlanExecutor` calls `verify_resource` after any creation task.

- [ ] **Step 3: Verify with mock runner**
Update `tests/test_execution.py` to assert that 'get' is called 3 times after a 'create'.

- [ ] **Step 4: Commit**
```bash
git add src/gws_assistant/execution/verifier.py src/gws_assistant/execution/executor.py
git commit -m "feat: implement triple-check verification layer"
```

---

### Task 4: Specialist Parallel Dispatch (Services)

**Action:** Dispatch 7 parallel subagents for service implementation.

- [ ] **Step 1: Prepare Specialist Bundle for each agent**
Construct the specific instruction set for Gmail, Drive, Sheets, Docs, Calendar, Tasks, and Keep specialists.

- [ ] **Step 2: Dispatch agents in parallel**
Use `dispatching-parallel-agents` to spawn the subagents.

- [ ] **Step 3: Aggregate reports and integrate code**
Review the summaries from all 7 subagents and integrate their `execution/` helpers and tests.

- [ ] **Step 4: Run full test suite**
Run: `pytest -v`
Expected: ALL PASS for 7 services.

- [ ] **Step 5: Final Commit**
```bash
git add .
git commit -m "feat: integrated full CRUD coverage and tests for 7 core services"
```
