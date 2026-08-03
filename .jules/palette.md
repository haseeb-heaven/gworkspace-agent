## 2024-07-13 - Visual Hierarchy and Keyboard Accessibility in Gradio
**Learning:** Gradio text inputs used for long tokens can stretch layouts awkwardly if not constrained. Additionally, primary action buttons should visually stand out from secondary actions, and forms should support keyboard submissions (Enter key) for accessibility.
**Action:** Use `max_lines=1` on token textboxes, apply `variant="primary"` to primary buttons, and bind `.submit()` events to textboxes.
