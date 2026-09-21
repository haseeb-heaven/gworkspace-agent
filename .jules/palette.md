## 2024-05-24 - Enhance Gradio UI inputs and primary buttons
**Learning:** Gradio buttons lack visual hierarchy by default, and text inputs for authentication tokens can stretch awkwardly if not limited. Adding `variant="primary"` to key actions and binding `.submit()` to inputs improves keyboard accessibility and visual flow.
**Action:** Always use `variant="primary"` for the main action in a form or row, and bind `.submit()` to textboxes used for authentication or single-line input to allow Enter-key submission.
