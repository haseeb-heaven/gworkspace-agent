## 2024-10-24 - Gradio Input and Button Polish
**Learning:** In Gradio applications, primary actions aren't visually distinct by default, and single-line token inputs can awkwardly stretch layout if pasted long tokens without max_lines restrictions. Also, users expect 'Enter' to submit forms on text inputs.
**Action:** Use `variant="primary"` for main action buttons (Run, Authenticate), `max_lines=1` for token/code textboxes to prevent layout shifts, and always bind `.submit()` events to text inputs for keyboard accessibility.
