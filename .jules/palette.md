## 2024-05-15 - Improve authentication UX and primary buttons
**Learning:** Users pasting long authorization codes in the Gradio textbox encounter awkward stretching, and primary actions lack visual distinction from secondary ones. Binding Enter-key submission to text inputs significantly improves flow.
**Action:** Add `max_lines=1` to inputs intended for tokens, use `variant="primary"` for main action buttons, and bind `.submit()` events to inputs to enable keyboard submission.
