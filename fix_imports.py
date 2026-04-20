from pathlib import Path

for p in list(Path('src').rglob('*.py')) + list(Path('tests').rglob('*.py')):
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue
    lines = text.splitlines()

    future_index = -1
    for i, line in enumerate(lines):
        if line.startswith('from __future__ import'):
            future_index = i

    if future_index != -1:
        # Check if there are any non-future imports or statements before future_index
        # If so, we need to move them after the last future import.
        import_os_lines = [i for i, line in enumerate(lines[:future_index+1]) if line == 'import os']
        if import_os_lines:
            for idx in reversed(import_os_lines):
                lines.pop(idx)
                future_index -= 1
            lines.insert(future_index + 1, 'import os')
            p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
