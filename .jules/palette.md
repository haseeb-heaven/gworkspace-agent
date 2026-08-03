## 2024-05-24 - Establish Clear Visual Hierarchy in Gradio
**Learning:** Gradio interfaces can suffer from poor visual hierarchy when primary and secondary actions (like "Run" and "Clear", or "Authenticate" and "Generate New Auth URL") are placed next to each other with the same default visual weight, leading to accidental clicks.
**Action:** Always assign `variant='primary'` to main action buttons to establish clear visual hierarchy and guide the user's focus appropriately.
