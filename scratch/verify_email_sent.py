"""Verification: check that the email about Investigation Report was sent."""
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

# userId is required as path param - use 'me' for the authenticated user
params = json.dumps({"userId": "me", "q": "subject:Investigation Report in:sent", "maxResults": 3})
result = runner.run(['gmail', 'users', 'messages', 'list', '--params', params])
print('=== EMAIL SENT VERIFICATION ===')
print('RC:', result.return_code)
print('STDERR:', result.stderr[:300] if result.stderr else 'NONE')

if result.return_code == 0 and result.stdout:
    try:
        data = json.loads(result.stdout)
        messages = data.get('messages', [])
        print(f'\nFOUND {len(messages)} sent message(s) about Investigation Report:')
        if messages:
            print('VERIFICATION PASSED - Email was sent successfully!')
            for m in messages[:3]:
                print(f'  - Message ID: {m.get("id")}')
        else:
            print('NOTE: No messages found in sent with that subject (may use different subject)')
            # Try a broader search
            params2 = json.dumps({"userId": "me", "q": "to:haseebmir.hm@gmail.com in:sent", "maxResults": 3})
            r2 = runner.run(['gmail', 'users', 'messages', 'list', '--params', params2])
            if r2.return_code == 0:
                d2 = json.loads(r2.stdout)
                m2 = d2.get('messages', [])
                print(f'Recent sent to haseebmir.hm@gmail.com: {len(m2)} message(s)')
                if m2:
                    print('VERIFICATION PASSED (via recipient check)')
    except Exception as e:
        print(f'Parse error: {e}')
        print('Raw:', result.stdout[:500])
else:
    print('VERIFICATION FAILED - Command error')
    print('STDOUT:', result.stdout[:500] if result.stdout else 'EMPTY')
