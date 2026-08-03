## 2024-05-15 - Visual Hierarchy in Gradio Forms
**Learning:** When primary actions (like "Run" or "Authenticate") are placed next to secondary actions (like "Clear" or "Regenerate URL") in Gradio without clear visual distinction, users can accidentally click the wrong button, leading to destructive or frustrating outcomes. Setting `variant="primary"` on the main action establishes a clear visual hierarchy.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio interfaces when placed adjacent to secondary actions.
