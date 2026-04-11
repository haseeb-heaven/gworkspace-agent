
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("src"))

from gws_assistant.planner import CommandPlanner

class MockPlanner(CommandPlanner):
    def __init__(self):
        pass # Skip init

planner = MockPlanner()
test_cases = [
    "Sheet1!A1",
    "Job Offers!A1",
    "'Job Offers'!A1",
    "Data!A1:B10",
    "Company Data!Z100",
]

for tc in test_cases:
    print(f"'{tc}' -> '{planner._format_range(tc)}'")
