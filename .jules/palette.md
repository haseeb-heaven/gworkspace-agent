## 2024-06-16 - Visual Hierarchy for Gradio Action Buttons
**Learning:** In Gradio UIs, primary actions placed adjacent to secondary actions (like "Run" next to "Clear") lack visual hierarchy by default, increasing the risk of accidental clicks on destructive or secondary actions.
**Action:** Always assign `variant='primary'` to the main action button in adjacent button groupings to establish clear visual dominance.
