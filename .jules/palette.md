## 2024-08-15 - Add primary buttons and enter-key submission to Gradio app
**Learning:** Textboxes used for long tokens or auth codes stretch awkwardly when pasted, and users expect to hit "Enter" to submit them instead of clicking a button. Primary buttons should be visually distinct from secondary actions in Gradio forms.
**Action:** Use `max_lines=1` for auth code inputs, bind `.submit()` events to inputs for enter-key submission, and add `variant="primary"` to primary action buttons.
