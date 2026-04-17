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
logger = logging.getLogger("manual_test_docs")

def test_docs():
    planner = CommandPlanner()
    runner = GWSRunner(Path("gws.exe"), logger)
    
    logger.info("Creating a Google Doc")
    args = planner.build_command("docs", "create_document", {
        "title": "Manual Test Validation: Phase 2 Docs"
    })
    
    result = runner.run(args)
    logger.info(f"Execution Success: {result.success}")
    if not result.success:
        logger.error(f"Error: {result.stderr}")
        return
        
    doc_data = json.loads(result.stdout)
    doc_id = doc_data.get("documentId")
    logger.info(f"Created doc with ID: {doc_id}")
    
    logger.info("Appending content to the document")
    args2 = planner.build_command("docs", "batch_update", {
        "document_id": doc_id,
        "text": "Hello from GWS Agent testing phase. This is the manual test validation for Docs."
    })
    res2 = runner.run(args2)
    logger.info(f"Update Success: {res2.success}")
    
    with open("doc_id.txt", "w") as f:
        f.write(doc_id)

if __name__ == "__main__":
    test_docs()
