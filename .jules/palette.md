## 2023-10-25 - Primary Buttons and Token Input Constraints
**Learning:** In Gradio applications, long token inputs can stretch layouts awkwardly without `max_lines=1`, and primary actions blend in with secondary actions without `variant="primary"`.
**Action:** Use `variant="primary"` for main action buttons (Run, Authenticate) and `max_lines=1` for auth token inputs to improve visual hierarchy and layout stability.
