import re
import json
import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

def _get_value_by_path(data: dict, path: str) -> Any:
    parts = path.split('.')
    curr: Any = data
    for i, part in enumerate(parts):
        index_match = re.search(r'\[(\d+)\]$', part)
        if index_match:
            index = int(index_match.group(1))
            name = part[:index_match.start()]
            if name:
                if isinstance(curr, dict):
                    val = curr.get(name)
                    if val is None:
                        if name.startswith("task-"):
                            num = name.removeprefix("task-")
                            val = curr.get(num) or curr.get(f"t{num}")
                    curr = val
            if isinstance(curr, dict) and not isinstance(curr, list):
                for list_key in ["messages", "files"]:
                    if list_key in curr and isinstance(curr[list_key], list):
                        curr = curr[list_key]
                        break
            if isinstance(curr, list) and 0 <= index < len(curr):
                curr = curr[index]
            else: return None
        else:
            if isinstance(curr, dict): curr = curr.get(part)
            else: return None
        if curr is None: return None
    return curr

def replace_match(match, results_map):
    p = (match.group(1) or match.group(2) or match.group(3) or "").strip()
    res = _get_value_by_path(results_map, p)
    if res is not None:
        if isinstance(res, (dict, list)): return json.dumps(res)
        return str(res)
    return match.group(0)

results_map = {
    "task-1": {"messages": [{"id": "m1"}]}
}

val = "import json; print(json.dumps({task-1}))"
regex = r'\{\{([\w\-\.\[\]]+)\}\}|\{([\w\-\.\[\]]+)\}|(\$task-[\w\-\.\[\]]+)'

new_val = re.sub(regex, lambda m: replace_match(m, results_map), val)
print(f"Input: {val}")
print(f"Output: {new_val}")
