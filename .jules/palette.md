## 2024-05-15 - Gradio Primary Buttons and Textbox Submission
**Learning:** In Gradio applications, primary actions like submitting authentication codes or running requests are not visually distinct by default, and textboxes for pasting tokens can stretch awkwardly. Also, users expect to submit single-line inputs by pressing Enter.
**Action:** Use `variant="primary"` on primary `gr.Button` elements. Use `max_lines=1` on `gr.Textbox` inputs intended for pasting tokens, and bind `.submit()` events to them to allow Enter-key submissions.
