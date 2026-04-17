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
logger = logging.getLogger("manual_test_sheets")

def test_sheets():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    logger.info("Creating a Google Sheet")
    args = planner.build_command("sheets", "create_spreadsheet", {
        "title": "Manual Test Validation: Phase 3 Sheets"
    })
    
    result = runner.run(args)
    if not result.success:
        logger.error(f"Error creating sheet: {result.stderr}")
        return
        
    sheet_data = json.loads(result.stdout)
    sheet_id = sheet_data.get("spreadsheetId")
    logger.info(f"Created sheet with ID: {sheet_id}")
    
    logger.info("Appending data to the sheet")
    args2 = planner.build_command("sheets", "append_values", {
        "spreadsheet_id": sheet_id,
        "range": "Sheet1!A1",
        "values": [["Name", "Role"], ["Alice", "Engineer"], ["Bob", "Manager"]]
    })
    res2 = runner.run(args2)
    logger.info(f"Update Success: {res2.success}")
    
    with open("sheet_id.txt", "w") as f:
        f.write(sheet_id)

if __name__ == "__main__":
    test_sheets()
