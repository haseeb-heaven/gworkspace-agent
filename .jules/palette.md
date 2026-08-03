## 2026-05-18 - Visual Hierarchy for Main Actions
**Learning:** In Gradio interfaces, when primary action buttons ('Run', 'Authenticate') are placed next to secondary buttons ('Clear', 'Generate New Auth URL'), users can easily click the wrong button if there's no visual distinction. Primary buttons need clear visual weight.
**Action:** Always assign `variant='primary'` to main action buttons in Gradio apps to establish clear visual hierarchy and prevent accidental destructive or secondary actions.
