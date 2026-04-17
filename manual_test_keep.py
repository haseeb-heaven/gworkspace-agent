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
logger = logging.getLogger("manual_test_keep")

def test_keep():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    logger.info("Creating a Google Keep Note")
    args = planner.build_command("keep", "create_note", {
        "title": "Manual Test Validation: Phase 4 Keep",
        "body": "Hello from GWS Agent testing phase. This is the manual test validation for Keep."
    })
    
    result = runner.run(args)
    logger.info(f"Execution Success: {result.success}")
    if not result.success:
        logger.error(f"Error: {result.stderr}")
        return
        
    note_data = json.loads(result.stdout)
    note_name = note_data.get("name") # Keep uses 'name' as ID usually (notes/...)
    logger.info(f"Created note with name: {note_name}")
    
    with open("keep_note_name.txt", "w") as f:
        f.write(note_name)

if __name__ == "__main__":
    test_keep()
