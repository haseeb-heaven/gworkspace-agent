## 2024-05-01 - Add Primary Button Variants
**Learning:** Gradio UI doesn't provide visual distinction between primary and secondary actions by default, which can lead to accidental clicks on destructive or clear buttons when placed together.
**Action:** Always assign `variant='primary'` to main action buttons (e.g., 'Run', 'Authenticate') when placed near secondary buttons to establish clear visual hierarchy.
