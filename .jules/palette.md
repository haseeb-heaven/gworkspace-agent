## 2024-05-18 - [Preventing Layout Shift on Token Inputs]
**Learning:** In Gradio applications, textboxes intended for pasting long, single-string tokens (like OAuth codes) can cause awkward layout stretching or unnecessary vertical expansion when users paste the code.
**Action:** Use `max_lines=1` on token/code textboxes to preserve layout stability and prevent vertical shift upon paste.
