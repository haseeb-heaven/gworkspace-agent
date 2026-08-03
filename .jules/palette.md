## 2024-07-07 - Add primary variant to main action buttons
**Learning:** Gradio UI lacked visual hierarchy for primary actions, making it harder for users to identify the primary next step among secondary buttons like "Clear" or "Generate New Auth URL".
**Action:** Always assign `variant='primary'` to main action buttons (e.g., 'Run', 'Authenticate') when they are placed near secondary buttons to establish clear visual hierarchy and prevent accidental clicks.
