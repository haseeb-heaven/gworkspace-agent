## 2024-05-24 - Gradio Button Visual Hierarchy
**Learning:** In the Gradio app, primary action buttons ("Run", "Authenticate") were visually identical to secondary buttons ("Clear", "Generate New Auth URL"). This lack of hierarchy can cause accidental clicks on secondary actions.
**Action:** Always assign `variant='primary'` to main action buttons when they are placed near secondary buttons to establish clear visual hierarchy in Gradio interfaces.
