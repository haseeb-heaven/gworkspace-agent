# GWorkspace Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute and validate all Google Workspace services sequentially with strict testing, error handling, commit discipline, and double verification.

**Architecture:** Sequential processing of each service. Each service undergoes manual testing, unit testing, and double verification. Telegram updates are sent at every step.

**Tech Stack:** Python, Pytest, GWS CLI, Telegram API.

---

### Task 1: Gmail (Email) Validation

**Files:**
- Manual Test: `tests/manual/gmail/test_manual_gmail.py`
- Unit Test: `tests/unit/gmail/test_gmail.py`

- [ ] **Step 1: Start Gmail Service Validation**
    - Run: `python send_telegram.py "Step 1: Starting Gmail Service Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/gmail/test_manual_gmail.py -v`
    - Expected: PASS

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/gmail/test_gmail.py -v`
    - Max 2 unit tests.
    - Expected: PASS

- [ ] **Step 4: Fix and Re-test if needed**
    - If any failure, fix code and re-run.

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: gmail validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Send an email via CLI: `python gws_cli.py --task 'send an email to haseebmir.hm@gmail.com with subject \"Validation Test\" and body \"This is a validation test.\"'`
    - 2. Verify via CLI (list messages): `python gws_cli.py --task 'list my latest 5 emails'`
    - Verify resources manually if possible or via CLI logs.

- [ ] **Step 7: Mark Gmail Complete**
    - Run: `python send_telegram.py "Gmail Service Validation COMPLETE. Moving to Google Docs."`

---

### Task 2: Google Docs Validation

**Files:**
- Manual Test: `tests/manual/docs/test_manual_docs.py`
- Unit Test: `tests/unit/docs/test_docs.py`

- [ ] **Step 1: Start Google Docs Validation**
    - Run: `python send_telegram.py "Step 2: Starting Google Docs Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/docs/test_manual_docs.py -v`

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/docs/test_docs.py -v`

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: docs validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Create a doc: `python gws_cli.py --task 'create a google doc named \"Validation Doc\" with content \"Hello World\"'`
    - 2. Read the doc: `python gws_cli.py --task 'read the content of doc named \"Validation Doc\"'`
    - Verify persistence.

- [ ] **Step 7: Mark Google Docs Complete**
    - Run: `python send_telegram.py "Google Docs Validation COMPLETE. Moving to Google Sheets."`

---

### Task 3: Google Sheets Validation

**Files:**
- Manual Test: `tests/manual/sheets/test_manual_sheets.py`
- Unit Test: `tests/unit/sheets/test_sheets.py` (Note: tests/unit/sheets/ exists but let's check files)

- [ ] **Step 1: Start Google Sheets Validation**
    - Run: `python send_telegram.py "Step 3: Starting Google Sheets Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/sheets/test_manual_sheets.py -v`

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/sheets/` (check files first)

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: sheets validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Create a sheet: `python gws_cli.py --task 'create a spreadsheet named \"Validation Sheet\"'`
    - 2. Append values: `python gws_cli.py --task 'append \"A1\", \"B1\" to \"Validation Sheet\"'`
    - 3. Read values: `python gws_cli.py --task 'read values from \"Validation Sheet\"'`
    - Verify data persistence.

- [ ] **Step 7: Mark Google Sheets Complete**
    - Run: `python send_telegram.py "Google Sheets Validation COMPLETE. Moving to Google Keep."`

---

### Task 4: Google Keep (Notes) Validation

**Files:**
- Manual Test: `tests/manual/search/test_manual_search.py` (Wait, where is Keep?)
- Actually Keep might be handled via gws directly. I should check `gws_cli.py` or service catalog.

- [ ] **Step 1: Start Google Keep Validation**
    - Run: `python send_telegram.py "Step 4: Starting Google Keep Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run manual test if exists or use CLI.

- [ ] **Step 3: Run Unit Test(s)**

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: keep validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Create a note: `python gws_cli.py --task 'create a keep note with title \"Validation Note\" and body \"Test\"'`
    - 2. List notes: `python gws_cli.py --task 'list my keep notes'`

- [ ] **Step 7: Mark Google Keep Complete**
    - Run: `python send_telegram.py "Google Keep Validation COMPLETE. Moving to Google Meet."`

---

### Task 5: Google Meet Validation

**Files:**
- Manual Test: `tests/manual/meet/test_manual_meet.py`
- Unit Test: `tests/unit/meet/test_meet.py`

- [ ] **Step 1: Start Google Meet Validation**
    - Run: `python send_telegram.py "Step 5: Starting Google Meet Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/meet/test_manual_meet.py -v`

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/meet/test_meet.py -v`

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: meet validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Create a meeting: `python gws_cli.py --task 'create a meet space'`
    - 2. Verify link: Check logs for meeting link.

- [ ] **Step 7: Mark Google Meet Complete**
    - Run: `python send_telegram.py "Google Meet Validation COMPLETE. Moving to Google Calendar."`

---

### Task 6: Google Calendar Validation

**Files:**
- Manual Test: `tests/manual/calendar/test_manual_calendar.py`
- Unit Test: `tests/unit/calendar/test_calendar.py`

- [ ] **Step 1: Start Google Calendar Validation**
    - Run: `python send_telegram.py "Step 6: Starting Google Calendar Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/calendar/test_manual_calendar.py -v`

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/calendar/test_calendar.py -v`

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: calendar validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Create event: `python gws_cli.py --task 'create a calendar event named \"Validation Event\" at tomorrow 10am'`
    - 2. List events: `python gws_cli.py --task 'list my calendar events for tomorrow'`

- [ ] **Step 7: Mark Google Calendar Complete**
    - Run: `python send_telegram.py "Google Calendar Validation COMPLETE. Moving to Google Drive."`

---

### Task 7: Google Drive Validation

**Files:**
- Manual Test: `tests/manual/drive/test_manual_drive.py`
- Unit Test: `tests/unit/drive/test_drive.py`

- [ ] **Step 1: Start Google Drive Validation**
    - Run: `python send_telegram.py "Step 7: Starting Google Drive Validation"`

- [ ] **Step 2: Run Manual Test**
    - Run: `pytest tests/manual/drive/test_manual_drive.py -v`

- [ ] **Step 3: Run Unit Test(s)**
    - Run: `pytest tests/unit/drive/test_drive.py -v`

- [ ] **Step 4: Fix and Re-test if needed**

- [ ] **Step 5: Commit changes**
    - Run: `git add . && git commit -m "test: drive validation complete"`

- [ ] **Step 6: Double Verification**
    - 1. Upload file: `python gws_cli.py --task 'upload file README.md to drive'`
    - 2. List files: `python gws_cli.py --task 'list my drive files named README.md'`

- [ ] **Step 7: Mark Google Drive Complete**
    - Run: `python send_telegram.py "Google Drive Validation COMPLETE. All services validated."`
