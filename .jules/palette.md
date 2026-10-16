## 2026-10-16 - Add copy buttons to Gradio Textbox components
**Learning:** `gr.Textbox` supports a dedicated `show_copy_button` argument (added in newer Gradio versions). Passing `buttons=["copy"]` is an invalid keyword and causes a `TypeError` on initialization.
**Action:** When adding copy buttons to read-only `gr.Textbox` components in Gradio, always use `show_copy_button=True` instead of the `buttons` array parameter.
