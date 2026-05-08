
import json
from gws_assistant.planner import CommandPlanner
from gws_assistant.models import CodeExecutionOutput

def test_append_values_with_model():
    planner = CommandPlanner()
    model_output = CodeExecutionOutput(parsed_value=[["Row 1", "Data"], ["Row 2", "Data"]])
    params = {
        "spreadsheet_id": "sheet123",
        "range": "Sheet1!A1",
        "values": model_output
    }
    command = planner.build_command("sheets", "append_values", params)

    # Check if the command contains the values from the model
    json_payload = command[command.index("--json") + 1]
    payload = json.loads(json_payload)
    assert payload["values"] == [["Row 1", "Data"], ["Row 2", "Data"]]
    print("Test append_values with model PASSED")

def test_append_values_with_dict():
    planner = CommandPlanner()
    dict_output = {"parsed_value": [["Row A", "Val"], ["Row B", "Val"]]}
    params = {
        "spreadsheet_id": "sheet123",
        "range": "Sheet1!A1",
        "values": dict_output
    }
    command = planner.build_command("sheets", "append_values", params)

    # Check if the command contains the values from the dict
    json_payload = command[command.index("--json") + 1]
    payload = json.loads(json_payload)
    assert payload["values"] == [["Row A", "Val"], ["Row B", "Val"]]
    print("Test append_values with dict PASSED")

if __name__ == "__main__":
    test_append_values_with_model()
    test_append_values_with_dict()
