## 2024-05-15 - Primary Action Identification
**Learning:** In Gradio applications, primary buttons like "Run" or "Authenticate" should use `variant="primary"` to distinguish them from secondary actions like "Clear". Also, input textboxes where users paste things like auth codes or type a single query are better with `max_lines=1` or `.submit()` bound to allow hitting Enter to submit, preventing awkward UX.
**Action:** Use `variant="primary"` on primary buttons and add `request.submit()` for Enter-key submission.
