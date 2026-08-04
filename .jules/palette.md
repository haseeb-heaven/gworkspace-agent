## 2026-08-04 - [Gradio Component UX Optimizations]
**Learning:** [Gradio primary actions can blend in with secondary actions, and textboxes for long tokens cause awkward layout stretching if `max_lines` isn't constrained. Further, missing Enter-key `.submit()` bindings on inputs breaks expected keyboard navigation patterns.]
**Action:** [Always use `variant="primary"` for primary buttons, `max_lines=1` for single-line token inputs, and bind `.submit()` events to inputs to support Enter-key submissions.]
