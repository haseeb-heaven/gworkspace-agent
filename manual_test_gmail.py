import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(os.path.abspath('src'))
load_dotenv()

from gws_assistant.planner import CommandPlanner
from gws_assistant.gws_runner import GWSRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manual_test")

def test_gmail():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    to_email = os.getenv("DEFAULT_RECIPIENT_EMAIL", "haseeb.heaven@gmail.com")
    logger.info(f"Sending email to {to_email}")
    
    args = planner.build_command("gmail", "send_message", {
        "to_email": to_email,
        "subject": "Manual Test Validation: Phase 1 Gmail",
        "body": "Hello from GWS Agent testing phase. This is the manual test validation for Gmail.",
        "attachments": "test_attachment.txt"
    })
    
    logger.info(f"Built command args: {args}")
    result = runner.run(args)
    logger.info(f"Execution Success: {result.success}")
    if not result.success:
        logger.error(f"Error: {result.stderr}")
    else:
        logger.info(f"Output: {result.stdout}")

if __name__ == "__main__":
    test_gmail()
