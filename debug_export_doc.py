
import sys
import os
import json
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "src"))

from gws_assistant.gws_runner import GWSRunner
from gws_assistant.models import AppConfigModel

def debug_export_doc():
    logger = logging.getLogger("debug")
    logging.basicConfig(level=logging.INFO)
    
    gws_exe = Path(os.getcwd()) / "gws.exe"
    runner = GWSRunner(gws_exe, logger)
    
    file_id = "1KvB1sNAdpIbwResYgPWYnLlcrJpsWaLHOZbp9pm0UIA"
    
    # Try to export as text/plain
    params = {
        "fileId": file_id,
        "mimeType": "text/plain"
    }
    output_file = f"scratch/exports/debug_export_{file_id}.txt"
    args = ["drive", "files", "export", "--params", json.dumps(params), "-o", output_file]
    
    print(f"Executing: {args}")
    result = runner.run(args)
    
    print("\n--- SUCCESS ---")
    print(result.success)
    
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
        print("\n--- CONTENT ---")
        print(content)
    else:
        print("\n--- ERROR: Output file not created ---")
        print(result.stderr)

if __name__ == "__main__":
    debug_export_doc()
