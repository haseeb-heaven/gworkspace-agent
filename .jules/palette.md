## 2024-05-24 - Gradio Interactive Elements Enhancements
**Learning:** Textboxes used for single-line tokens can stretch awkwardly in Gradio. Primary action buttons blend in with secondary actions if not explicitly marked. Users expect Enter to submit forms.
**Action:** Set `max_lines=1` on token textboxes. Use `variant="primary"` on primary buttons. Bind `.submit()` event to textboxes to mirror primary action clicks.
