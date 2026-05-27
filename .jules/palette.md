## 2024-05-24 - Gradio Visual Hierarchy
**Learning:** Gradio interfaces can lack clear visual hierarchy when primary actions (like "Run" or "Authenticate") and secondary actions (like "Clear" or "Generate New Auth URL") look visually identical, which can lead to accidental clicks.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio to establish a clear visual hierarchy and guide the user's attention to the most important actions.
