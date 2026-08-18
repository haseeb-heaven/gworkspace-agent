## 2024-05-24 - Primary Buttons and Enter-key Submission in Gradio
**Learning:** Users naturally press Enter after pasting tokens or long strings. Additionally, primary actions (like authentication or running tasks) blend in with secondary actions without visual distinction.
**Action:** Use `variant="primary"` on primary `gr.Button` elements, bind `.submit()` events to `gr.Textbox` inputs to allow Enter-key submissions, and use `max_lines=1` on token textboxes to prevent awkward layout stretching.
