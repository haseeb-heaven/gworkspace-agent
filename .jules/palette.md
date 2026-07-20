## 2024-05-24 - Primary Actions and Input UX
**Learning:** In Gradio applications, primary actions (like "Run" or "Authenticate") blend in with secondary actions unless explicitly styled. Textboxes for pasting tokens (like auth codes) stretch awkwardly without line constraints. Users also expect to submit single-line forms via the Enter key.
**Action:** Used `variant="primary"` on primary buttons, added `max_lines=1` to the auth token input, and bound `.submit()` to the token input to support Enter-key submissions.
