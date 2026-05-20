## 2026-05-20 - Visual Hierarchy with Gradio Button Variants
**Learning:** In Gradio interfaces with multiple adjacent buttons (like 'Run' next to 'Clear', or 'Authenticate' next to 'Generate New Auth URL'), failing to establish a visual hierarchy often leads to accidental clicks on destructive or secondary actions.
**Action:** Always assign `variant='primary'` to the primary action `gr.Button` to visually distinguish it from secondary buttons (which default to `variant='secondary'`). This guides the user's focus and reduces interaction errors.
