## $(date +%Y-%m-%d) - Gradio Form UX Improvements
**Learning:** In Gradio applications, primary actions (like "Run" or "Authenticate") blend in with secondary actions unless explicitly styled. Additionally, users expect standard form behaviors, such as pressing Enter to submit and single-line inputs for tokens.
**Action:** Use `variant="primary"` on primary `gr.Button` elements, bind `.submit()` events to `gr.Textbox` inputs to allow Enter-key submissions, and use `max_lines=1` on textboxes intended for pasting long tokens to prevent awkward layout stretching.
