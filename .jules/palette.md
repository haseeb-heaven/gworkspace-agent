## 2024-06-26 - Visual Hierarchy with Primary Buttons
**Learning:** Users can accidentally click secondary actions when main and secondary buttons have the same visual weight. Gradio defaults all buttons to the 'secondary' variant, making the UI less intuitive.
**Action:** Always assign `variant='primary'` to main action buttons (e.g., 'Run', 'Authenticate') when placed near secondary buttons to establish clear visual hierarchy and prevent misclicks.
