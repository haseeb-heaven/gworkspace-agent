## 2024-07-24 - Primary action variants in Gradio
**Learning:** Gradio UI doesn't visually distinguish primary and secondary buttons by default, which can lead to accidental clicks on destructive or secondary actions like "Clear" when they are next to main actions like "Run".
**Action:** Always assign `variant='primary'` to main action buttons when they are placed near secondary buttons to establish clear visual hierarchy.
