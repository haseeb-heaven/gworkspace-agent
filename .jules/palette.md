## 2024-05-24 - Primary action buttons in Gradio interfaces
**Learning:** Gradio UI doesn't visually differentiate between primary and secondary actions by default, which can cause users to accidentally click secondary actions (like "Clear" instead of "Run").
**Action:** Always assign `variant='primary'` to main action buttons when they are placed adjacent to secondary buttons to establish clear visual hierarchy.
