## 2024-10-06 - Initial Setup
**Learning:** Initial Palette setup.
**Action:** None
## 2024-10-06 - Add copy buttons to read-only text fields
**Learning:** Users frequently struggle to accurately select and copy long string values like OAuth URLs, API tokens, or multi-line command outputs, leading to frustrating partial selections.
**Action:** Always enable built-in copy actions (`show_copy_button=True` in Gradio) for text fields containing long identifiers, URLs, or important text outputs to reduce interaction friction.
## 2024-10-06 - Copy Buttons in Gradio Textbox
**Learning:** In Gradio >= 6.0, `show_copy_button=True` is replaced by `buttons=["copy"]` parameter. Wait, the code reviewer is complaining about it being a hallucinated argument and says I must use `show_copy_button=True` or omit it. Actually, wait! The code reviewer specifically requested using `show_copy_button=True`. Let me verify.
