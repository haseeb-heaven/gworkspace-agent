# Implementation Plan: GWorkspace Automation Tasks

**Goal:** Implement and test three automation tasks: GDrive-to-Gmail, Web-to-Sheets, and Code Execution sorting.

**Architecture:** Utilize `src/gws_assistant/service_catalog.py` and `src/gws_assistant/execution.py` to bridge user intents to service actions. Tools in `src/gws_assistant/tools/` will handle data processing.

**Tech Stack:** Python, LangChain, pytest, Google Workspace SDK (via `gws` binary).

---

### Task 1: GDrive to Gmail integration
- [ ] **Step 1: Write failing test** (Create `tests/test_drive_to_gmail.py`)
- [ ] **Step 2: Implement and Verify** (Update `service_catalog.py` if needed, implement in `execution.py`)
- [ ] **Step 3: Commit**

### Task 2: Web Search to Google Sheets
- [ ] **Step 1: Write failing test** (Create `tests/test_search_to_sheets.py`)
- [ ] **Step 2: Implement and Verify** (Update `service_catalog.py` if needed)
- [ ] **Step 3: Commit**

### Task 3: Code Execution Sorting
- [ ] **Step 1: Write failing test** (Create `tests/test_code_sort.py`)
- [ ] **Step 2: Implement and Verify** (`src/gws_assistant/tools/code_execution.py`)
- [ ] **Step 3: Commit**
