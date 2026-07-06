## 2024-07-06 - Establish visual hierarchy for primary actions
**Learning:** In form interfaces with multiple side-by-side actions (like Run/Clear or Authenticate/Regenerate), users can accidentally trigger destructive or secondary actions if all buttons carry the same visual weight. Gradio defaults to uniform button styling which exacerbates this.
**Action:** Always assign `variant='primary'` to main action buttons (e.g., 'Run', 'Authenticate') when placed adjacent to secondary/destructive buttons to establish clear visual hierarchy and prevent accidental clicks.
