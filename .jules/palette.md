## 2024-05-24 - Gradio Primary Actions & Input Ergonomics
**Learning:** Users pasting long auth tokens often experience awkward layout stretching, and primary actions are easily confused with secondary ones.
**Action:** Apply `variant="primary"` to primary buttons (Authenticate, Run), use `max_lines=1` for single-line inputs like tokens, and bind `.submit()` for Enter-key submission on inputs.
