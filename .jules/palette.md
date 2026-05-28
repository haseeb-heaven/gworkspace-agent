## 2024-05-15 - Visual Hierarchy for Main Actions in Gradio
**Learning:** In Gradio interfaces, primary actions (like "Run" or "Authenticate") can blend in with secondary actions (like "Clear" or "Generate New Auth URL") if they share the same default styling, leading to accidental clicks or confusion.
**Action:** Always assign `variant='primary'` to main action buttons when they are placed near secondary buttons to establish a clear visual hierarchy.
