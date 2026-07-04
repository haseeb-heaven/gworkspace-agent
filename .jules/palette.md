## 2024-05-24 - Establish visual hierarchy in Gradio forms
**Learning:** Gradio default buttons all look the same, making primary actions (like "Run" or "Authenticate") blend in with secondary actions (like "Clear"). This can lead to accidental clicks.
**Action:** Always assign `variant='primary'` to main action buttons when placed next to secondary buttons.
