## 2024-06-15 - Visual Hierarchy in Gradio Layouts
**Learning:** Gradio defaults all `gr.Button` components to a secondary styling variant, resulting in a lack of visual hierarchy when primary actions (like "Run" or "Authenticate") are placed adjacent to secondary actions (like "Clear"). This pattern in the application's forms increases the risk of accidental clicks.
**Action:** Always assign `variant='primary'` to the primary action buttons in `gr.Row` layouts to establish clear visual distinction.
