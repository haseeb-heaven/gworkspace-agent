## 2024-05-24 - Establish button visual hierarchy
**Learning:** The Gradio interface default buttons lack visual distinction, leading to potential accidental clicks on secondary actions like "Clear" or "Generate New Auth URL". Applying the `variant='primary'` to main action buttons establishes a clearer visual hierarchy.
**Action:** When building Gradio interfaces, always assign `variant='primary'` to main action buttons placed near secondary buttons.
