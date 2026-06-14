## 2024-06-25 - Gradio Button Visual Hierarchy
**Learning:** In Gradio interfaces with multiple buttons (like Run/Clear or Authenticate/Generate New Auth URL), lack of explicit styling makes it hard for users to immediately identify the primary action, increasing the risk of accidental clicks on secondary actions.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio to establish a clear visual hierarchy.
