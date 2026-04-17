import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(os.path.abspath('src'))
load_dotenv()

from gws_assistant.planner import CommandPlanner
from gws_assistant.gws_runner import GWSRunner
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manual_test_meet")

def test_meet():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    logger.info("Creating a Google Meet Meeting")
    args = planner.build_command("meet", "create_meeting", {})
    
    result = runner.run(args)
    logger.info(f"Execution Success: {result.success}")
    if not result.success:
        logger.error(f"Error: {result.stderr}")
        return
        
    meet_data = json.loads(result.stdout)
    meet_uri = meet_data.get("meetingUri")
    logger.info(f"Created meeting with URI: {meet_uri}")
    
    with open("meet_uri.txt", "w") as f:
        f.write(meet_uri)

if __name__ == "__main__":
    test_meet()
