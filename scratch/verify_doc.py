"""Verification script: check that 'Investigation Report' doc was created."""
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from gws_assistant.config import AppConfig
from gws_assistant.gws_runner import GWSRunner
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger('verify')
config = AppConfig.from_env()
runner = GWSRunner(config.gws_binary_path, logger=logger, config=config)

# Search for the doc via files list using --params
params = json.dumps({"q": 'name contains "Investigation Report"', "pageSize": 5})
result = runner.run(['drive', 'files', 'list', '--params', params])
print('=== DOC VERIFICATION ===')
print('RC:', result.return_code)
print('STDERR:', result.stderr[:500] if result.stderr else 'NONE')

if result.return_code == 0 and result.stdout:
    try:
        data = json.loads(result.stdout)
        files = data.get('files', [])
        print(f'\nFOUND {len(files)} file(s) matching "Investigation Report":')
        for f in files:
            print(f'  - {f.get("name")} (id={f.get("id")}, type={f.get("mimeType")})')
        if files:
            print('\nVERIFICATION PASSED - Doc was created successfully!')
        else:
            print('\nVERIFICATION FAILED - No matching files found')
    except Exception as e:
        print(f'Parse error: {e}')
        print('Raw:', result.stdout[:500])
else:
    print('VERIFICATION FAILED - Command error')
    print('STDOUT:', result.stdout[:500] if result.stdout else 'EMPTY')
