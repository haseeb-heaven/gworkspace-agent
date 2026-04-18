
import sys
import os
import json
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import AppConfigModel

def read_sheet_data():
    logger = logging.getLogger("debug")
    logging.basicConfig(level=logging.INFO)
    
    gws_exe = Path(os.getcwd()) / "gws.exe"
    runner = GWSRunner(gws_exe, logger)
    
    spreadsheet_id = "1R1Y_8V_LwcRpbqi_vRn5htbAZVk8BSQfIkn2UpEjEAY"
    
    # Try to read the whole sheet
    args = ["sheets", "+read", "--spreadsheet", spreadsheet_id, "--range", "A1:Z100"]
    
    print(f"Executing with GWSRunner: {args}")
    result = runner.run(args)
    
    print("\n--- SUCCESS ---")
    print(result.success)
    print("\n--- STDOUT ---")
    print(result.stdout)
    print("\n--- ERROR ---")
    print(result.error)

if __name__ == "__main__":
    read_sheet_data()
