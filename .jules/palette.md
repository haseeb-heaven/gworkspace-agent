## 2024-06-12 - Primary Action Button Variants
**Learning:** Gradio interface layouts placing primary actions (like 'Authenticate' or 'Run') next to secondary actions (like 'Generate New Auth URL' or 'Clear') lack visual hierarchy by default.
**Action:** Always assign `variant='primary'` to main action buttons when they are grouped with secondary buttons to establish clear visual distinction and prevent accidental destructive clicks.
