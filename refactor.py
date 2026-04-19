import re
from pathlib import Path

# Fix pytest.ini
ini = Path('pytest.ini')
if ini.exists():
    ini.write_text(ini.read_text(encoding='utf-8').replace('not manual and (gmail or docs or sheets or drive)', 'not manual and (gmail or docs or sheets or drive or calendar)'), encoding='utf-8')

# Replace hardcoded user@example.com fallback with no fallback
for p in list(Path('src').rglob('*.py')) + list(Path('tests').rglob('*.py')):
    try:
        text = p.read_text(encoding='utf-8')
    except Exception:
        continue

    new_text = re.sub(r'os\.getenv\("DEFAULT_RECIPIENT_EMAIL",\s*"[^"]*"\)', 'os.getenv("DEFAULT_RECIPIENT_EMAIL")', text)
    new_text = new_text.replace('"user@example.com"', 'os.getenv("DEFAULT_RECIPIENT_EMAIL")')
    new_text = new_text.replace("'user@example.com'", 'os.getenv("DEFAULT_RECIPIENT_EMAIL")')

    # Fix gws.exe
    new_text = new_text.replace('"gws.exe"', 'os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")')
    new_text = new_text.replace("'gws.exe'", 'os.getenv("GWS_BINARY_PATH", "gws.exe" if os.name == "nt" else "gws")')

    if text != new_text:
        # Add import os if not present
        if 'import os' not in new_text and 'import os\n' not in new_text and 'from os import' not in new_text:
            new_text = 'import os\n' + new_text
        p.write_text(new_text, encoding='utf-8')
