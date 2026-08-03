## 2024-05-20 - Visual Hierarchy for Main Actions
**Learning:** Gradio interfaces can look flat and ambiguous when multiple buttons are placed side-by-side (e.g., "Run" vs "Clear", "Authenticate" vs "Generate New Auth URL"). This causes hesitation and potential accidental clicks.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio to establish a clear visual hierarchy and guide the user to the expected primary action.
