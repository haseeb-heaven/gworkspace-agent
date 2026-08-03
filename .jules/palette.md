## 2024-05-11 - Gradio Primary Button Visual Hierarchy
**Learning:** In Gradio applications with multiple buttons in a row, users can accidentally click destructive or secondary actions (like "Clear" or "Regenerate") if all buttons look the same. Assigning `variant='primary'` to main action buttons (like "Run" or "Authenticate") establishes a clear visual hierarchy and prevents accidental clicks.
**Action:** Always assign `variant='primary'` to the primary action button when it's placed near secondary buttons in Gradio interfaces.
