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
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("manual_test_calendar")

def test_calendar():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    logger.info("Creating a Google Calendar Event")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    args = planner.build_command("calendar", "create_event", {
        "summary": "Manual Test Validation: Phase 6 Calendar",
        "start_date": tomorrow,
        "description": "Hello from GWS Agent testing phase. This is the manual test validation for Calendar."
    })
    
    result = runner.run(args)
    logger.info(f"Execution Success: {result.success}")
    if not result.success:
        logger.error(f"Error: {result.stderr}")
        return
        
    event_data = json.loads(result.stdout)
    event_id = event_data.get("id")
    logger.info(f"Created event with ID: {event_id}")
    
    with open("calendar_event_id.txt", "w") as f:
        f.write(event_id)

if __name__ == "__main__":
    test_calendar()
