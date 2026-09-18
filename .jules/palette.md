## 2024-10-25 - Gradio Primary Actions and Inputs
**Learning:** In Gradio applications, differentiating primary actions (like "Run" or "Authenticate") from secondary ones using `variant="primary"` improves clarity, and limiting long token inputs with `max_lines=1` prevents awkward UI stretching. Also, users expect to submit text fields by pressing Enter.
**Action:** Always use `variant="primary"` for the main actions in a form or view, set `max_lines=1` for token/code inputs, and bind `.submit()` events to inputs to support keyboard submissions.
