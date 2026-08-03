## 2024-07-16 - Primary Buttons and Enter Key Submit UX
**Learning:** Using `variant="primary"` helps clearly identify primary call-to-actions. Limiting textbox size with `max_lines=1` prevents layout stretching when pasting tokens. Binding `.submit()` on Textbox components allows Enter-key form submission which feels natural.
**Action:** Always use `variant="primary"` for primary buttons, set `max_lines=1` for single-line tokens/keys, and bind `.submit()` for enter-key submission in Gradio apps.
