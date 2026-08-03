## 2024-05-24 - Gradio Component Polish
**Learning:** Gradio interfaces can feel unpolished without explicit primary action styling (`variant="primary"`) and keyboard support (Enter-to-submit on inputs). Textboxes intended for tokens or codes can awkwardly stretch the layout if `max_lines=1` is not set.
**Action:** Always apply `variant="primary"` to primary actions, add `.submit()` bindings to input textboxes, and enforce `max_lines=1` for single-line tokens.
