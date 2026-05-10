## 2024-10-27 - Gradio Button Visual Hierarchy
**Learning:** Default Gradio buttons within `gr.Row` appear identical, creating an ambiguous layout where destructive/secondary actions (like "Clear") hold the same visual weight as primary actions (like "Run"). This is especially problematic in side-by-side layouts.
**Action:** Always assign `variant="primary"` to the main action button (e.g., "Run", "Authenticate", "Submit") when it is placed next to a secondary action button to establish clear visual hierarchy and prevent accidental clicks.
