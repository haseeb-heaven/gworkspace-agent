## 2024-09-22 - Enhance Primary Actions and Input UX
**Learning:** Primary actions should be visually distinct from secondary actions to guide users, and inputs intended for single-line tokens shouldn't stretch awkwardly. Supporting the Enter key for submission speeds up the workflow.
**Action:** Added `variant="primary"` to main action buttons, `max_lines=1` to the authorization code input, and mapped the Enter key to trigger the authentication flow.
