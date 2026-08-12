## 2026-08-12 - 🎨 Palette: Form and Interaction Micro-UX
**Learning:** Binding Enter-key `.submit()` events and setting input dimensions (`max_lines=1`) alongside visual hierarchy (`variant="primary"`) significantly smooths the auth flow in Gradio apps where users often paste single-line tokens.
**Action:** Default to max_lines=1 for single-line token inputs and bind submit events to textboxes in future Gradio forms.
