## 2023-10-10 - Add Copy Buttons to Gradio Output Textboxes
**Learning:** Users often need to copy output from tools (like the result or planned tasks in this Google Workspace Assistant). Currently, they have to manually select the text which can be tedious for long outputs.
**Action:** Use `show_copy_button=True` in Gradio Textbox components where users are likely to want to copy the contents, such as "Result", "Planned Tasks", and "Authorization URL".
