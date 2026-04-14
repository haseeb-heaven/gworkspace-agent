import re
import json
from typing import Any

def _get_value_by_path(data: dict, path: str) -> Any:
    """Evaluate a path like 'task-1[0].id' against task_results."""
    parts = path.split('.')
    curr: Any = data
    
    for part in parts:
        index_match = re.search(r'\[(\d+)\]$', part)
        if index_match:
            index = int(index_match.group(1))
            name = part[:index_match.start()]
            if name:
                if isinstance(curr, dict):
                    curr = curr.get(name)
                else:
                    print(f"DEBUG: curr is not dict for name='{name}': {type(curr)}")
                    return None
            
            if isinstance(curr, dict) and not isinstance(curr, list):
                # AUTO-UNWRAP
                for list_key in ["files", "messages", "items", "events", "values", "threads", "connections", "results", "rows"]:
                    if list_key in curr and isinstance(curr[list_key], list):
                        curr = curr[list_key]
                        break
            
            if isinstance(curr, list) and 0 <= index < len(curr):
                curr = curr[index]
            else:
                print(f"DEBUG: curr is not list or index out of range for index={index}: {type(curr)}")
                return None
        else:
            if isinstance(curr, dict):
                curr = curr.get(part)
            else:
                print(f"DEBUG: curr is not dict for part='{part}': {type(curr)}")
                return None
        
        if curr is None:
            return None
            
    return curr

# Mock data based on logs
results_map = {
    "task-1": {
        "messages": [
            {"id": "msg_id_1", "threadId": "thread_1"},
            {"id": "msg_id_2", "threadId": "thread_2"}
        ],
        "resultSizeEstimate": 201
    },
    "1": {
        "messages": [
            {"id": "msg_id_1", "threadId": "thread_1"},
            {"id": "msg_id_2", "threadId": "thread_2"}
        ],
        "resultSizeEstimate": 201
    }
}

path = "task-1[0].id"
result = _get_value_by_path(results_map, path)
print(f"Path: {path} -> Result: {result}")

path2 = "1[0].id"
result2 = _get_value_by_path(results_map, path2)
print(f"Path: {path2} -> Result: {result2}")
