## 2024-05-18 - [Primary Actions and Enter Key Submissions in Gradio]
**Learning:** Primary buttons and single-line text inputs (with Enter key submission) significantly improve the flow of authentication forms and main action triggers in Gradio applications, preventing layout stretching and confusing secondary actions.
**Action:** Always use `variant="primary"` for primary actions (like Submit/Run), add `max_lines=1` for token/code inputs, and bind `.submit()` events to textboxes that serve as form inputs.
