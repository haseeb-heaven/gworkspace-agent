## 2024-05-24 - [Visual Hierarchy in Gradio]
**Learning:** Gradio buttons default to secondary styling, causing primary actions like 'Run' and 'Authenticate' to blend in with secondary actions like 'Clear' or 'Generate New Auth URL', leading to potential accidental clicks or a lack of clear direction for the user.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio interfaces when placed near secondary buttons to establish clear visual hierarchy.
