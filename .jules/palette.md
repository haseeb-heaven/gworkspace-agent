## 2024-05-15 - Initial Journal
**Learning:** Initial Palette memory file created to track UX improvements.
**Action:** Use this file to log critical UX/a11y learnings based on changes made.
## 2024-05-15 - Primary Variants for Main Actions
**Learning:** Placing secondary actions visually equal to primary actions leads to confusion and accidental clicks. Adding `variant="primary"` to main action buttons in Gradio establishes a clear visual hierarchy.
**Action:** Always assign `variant="primary"` to the main submit or run buttons when they are adjacent to secondary buttons like 'Clear' or 'Regenerate'.
