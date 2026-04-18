
import sys
import os
import json
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import AppConfigModel

def list_12th_class_files():
    logger = logging.getLogger("debug")
    logging.basicConfig(level=logging.INFO)
    
    gws_exe = Path(os.getcwd()) / "gws.exe"
    runner = GWSRunner(gws_exe, logger)
    
    # Build params safely as a dict
    params = {
        "q": "name contains '12th Class' and mimeType = 'application/vnd.google-apps.document'",
        "pageSize": 10,
        "fields": "files(id, name, mimeType)"
    }
    
    args = ["drive", "files", "list", "--params", json.dumps(params)]
    
    print(f"Executing with GWSRunner: {args}")
    result = runner.run(args)
    
    print("\n--- SUCCESS ---")
    print(result.success)
    print("\n--- STDOUT ---")
    print(result.stdout)
    print("\n--- ERROR ---")
    print(result.error)

if __name__ == "__main__":
    list_12th_class_files()
