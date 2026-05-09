# Releases

## v1.0.1 - 2026-05-05

### Changes
- Add STATS.md with repository statistics in table format and reference in README
- Update pre-push hook to only check for Python files
- Update pre-push hook to run unit tests only on code changes
- Add Star History section to README
- Fix failing manual integration tests
- Fix tmp_path fixture issue and add missing pytest markers
- Remove gws_only markers from manual tests and revert shared.py changes
- Update calendar CRUD tests with real event ID from user's calendar
- Add chat and meet markers to pytest.ini and update calendar test with event ID
- Add comprehensive CRUD tests for all Google Workspace services
- Add service markers to gws_binary tests and filtering logic
- Add tests for all remaining gws.exe services
- Add unit tests for direct gws.exe binary commands
- Add 5 step verification to all manual tests
- Fully ignore scratch folder
- Fix verification: downgrade empty values error to WARNING for sheets append
- Fix execution: sanitize [File: ...] patterns in code results before sheets append
- Fix workflow: chain of fixes for drive-to-sheets-to-email task
- Fix models: skip stub validation for drive.export_file file_id
- Fix verification: allow placeholders in params, block only in results
- Fix verification: only block unresolved placeholders in result data, not params
- feat(gradio): add multi-user OAuth authentication flow
- chore(deps): bump actions/upload-artifact from 4 to 7
- chore(deps): bump actions/download-artifact from 4 to 8
- chore(deps): bump google-github-actions/deploy-cloudrun from 2 to 3
- chore(deps): bump google-github-actions/auth from 2 to 3
- chore(deps): bump google-github-actions/setup-gcloud from 2 to 3
- chore(deps): update ddgs requirement from >=9.13.0 to >=9.14.2
- chore(deps): update python-telegram-bot requirement
- chore(deps): bump python from 3.11-slim to 3.14-slim
- Configure Dependabot for multiple ecosystems
- Create dependabot.yml for version updates
- fix(agent): prevent DoS via regex backtracking in heuristic computation
- fix(verification): always detect unresolved placeholders regardless of path validation
- chore(release): rename tags to 0.1.0-0.5.0 and update changelog
- chore(release): add changelog entries for v0.0.6 to v0.0.10
- docs: update changelog history and add release reference to README

---
