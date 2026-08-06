## 2024-08-06 - Gradio Auth & Action UX
**Learning:** In Gradio applications, primary actions lack visual hierarchy by default, and pasting long tokens into textboxes causes awkward layout stretching. Additionally, users expect to submit single-line inputs (like auth codes) by pressing Enter.
**Action:** Always apply `variant="primary"` to main action buttons, use `max_lines=1` for token inputs to prevent stretching, and bind `.submit()` events to inputs alongside their respective button clicks.
