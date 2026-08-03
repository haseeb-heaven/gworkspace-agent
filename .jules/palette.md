## 2024-05-15 - Visual Hierarchy in Gradio Forms
**Learning:** Main action buttons like "Run" and "Authenticate" in Gradio often blend in with secondary actions (like "Clear" or "Generate New Auth URL"). This lacks clear visual hierarchy, potentially confusing users or leading to accidental clicks on the secondary action.
**Action:** Always assign `variant='primary'` to main action buttons when they are placed near secondary buttons to establish clear visual hierarchy and guide the user's attention.
