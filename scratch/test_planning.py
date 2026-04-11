import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gws_assistant.config import AppConfig
from gws_assistant.langchain_agent import plan_with_langchain
from gws_assistant.models import RequestPlan

def test_planning():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("test")
    
    config = AppConfig.from_env()
    text = "List all emails i received from amrita.priyadarshini@rockstarindia.com person and save all email to Google document and Send email to haseebmir.hm@gmail.com and append the link of those sheets and also attach as attachment."
    
    print(f"Testing planning for: {text}")
    print(f"Using model: {config.model}")
    print(f"Using provider: {config.provider}")
    
    plan = plan_with_langchain(text, config, logger)
    
    if plan:
        print("\nSUCCESS: Plan generated!")
        print(f"Summary: {plan.summary}")
        print(f"Tasks: {len(plan.tasks)}")
        for i, task in enumerate(plan.tasks, 1):
            print(f"  {i}. {task.service}.{task.action} - {task.reason}")
            print(f"     Params: {task.parameters}")
    else:
        print("\nFAILURE: Planning failed (returned None).")

if __name__ == "__main__":
    test_planning()
