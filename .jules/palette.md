## 2024-10-24 - Enhance Gradio Primary Actions and Input Handling
**Learning:** In Gradio applications, primary action buttons lack visual distinction by default, long token inputs can stretch layouts awkwardly when pasted, and textboxes don't support Enter-key submissions automatically, which breaks keyboard accessibility.
**Action:** Use `variant="primary"` for main action buttons (like Run or Authenticate) to guide the user's focus. Set `max_lines=1` on token/code textboxes to constrain layout. Bind `.submit()` events to textboxes to allow seamless Enter-key submissions.
