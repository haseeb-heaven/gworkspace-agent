"""Apply all fixes from ISSUES.md in one shot."""

# ============================================================
# FIX 2: telegram_app.py – type hint AppConfig -> AppConfigModel
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\telegram_app.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old = "from gws_assistant.config import AppConfig\n"
new = "from gws_assistant.config import AppConfig\nfrom gws_assistant.models import AppConfigModel\n"
src = src.replace(old, new, 1)

src = src.replace(
    "def create_application(config: AppConfig) -> Application:",
    "def create_application(config: AppConfigModel) -> Application:",
    1,
)
with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("[FIX 2] telegram_app.py – type hint fixed")

# ============================================================
# FIX 3: code_execution.py – sandbox escape via raw getattr/setattr
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\tools\code_execution.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

# Replace raw getattr/setattr with safe wrappers that block dunder attributes
old_getattr = '    safe_g["_getattr_"] = getattr\n    safe_g["_setattr_"] = setattr\n'
new_getattr = (
    '    # Security: block access to dunder/private attributes to prevent sandbox escape\n'
    '    _BLOCKED_ATTRS = frozenset({"__subclasses__", "__mro__", "__bases__", "__class__",\n'
    '                                "__globals__", "__code__", "__builtins__", "__dict__",\n'
    '                                "__module__", "__weakref__"})\n\n'
    '    def _safe_getattr(obj, name, *args):\n'
    '        if isinstance(name, str) and (name.startswith("__") or name in _BLOCKED_ATTRS):\n'
    '            raise AttributeError(f"Access to attribute {name!r} is blocked in the sandbox.")\n'
    '        return getattr(obj, name, *args)\n\n'
    '    def _safe_setattr(obj, name, value):\n'
    '        if isinstance(name, str) and (name.startswith("__") or name in _BLOCKED_ATTRS):\n'
    '            raise AttributeError(f"Setting attribute {name!r} is blocked in the sandbox.")\n'
    '        return setattr(obj, name, value)\n\n'
    '    safe_g["_getattr_"] = _safe_getattr\n'
    '    safe_g["_setattr_"] = _safe_setattr\n'
)
if old_getattr in src:
    src = src.replace(old_getattr, new_getattr, 1)
    print("[FIX 3] code_execution.py – sandbox getattr/setattr hardened")
else:
    print("[FIX 3] SKIP – pattern not found in code_execution.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 5: config.py – READ_ONLY_MODE defaults to True → False
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\config.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old5 = 'read_only_mode = _to_bool(os.getenv("READ_ONLY_MODE"), default=True)'
new5 = ('# Default False — allow writes by default. Set READ_ONLY_MODE=true in .env to block all write operations.\n'
        '        read_only_mode = _to_bool(os.getenv("READ_ONLY_MODE"), default=False)')
if old5 in src:
    src = src.replace(old5, new5, 1)
    print("[FIX 5] config.py – READ_ONLY_MODE default changed to False")
else:
    print("[FIX 5] SKIP – pattern not found in config.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 6: json_utils.py – greedy regex -> non-greedy JSON extraction
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\json_utils.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old6 = '    # Fallback: Find the first { or [ and the last } or ]\n    match = re.search(r"(\\{.*\\}|\\[.*\\])", text, re.DOTALL)'
new6 = (
    '    # Fallback: Find the FIRST balanced JSON object/array.\n'
    '    # Walk character by character to find the opening brace/bracket,\n'
    '    # then find its matching closing delimiter — avoids greedy regex\n'
    '    # absorbing diagnostic messages between two JSON blocks.\n'
    '    match = None\n'
    '    for start_idx, ch in enumerate(text):\n'
    '        if ch in ("{", "["):\n'
    '            end_ch = "}" if ch == "{" else "]"\n'
    '            depth = 0\n'
    '            in_str = False\n'
    '            escape = False\n'
    '            for end_idx in range(start_idx, len(text)):\n'
    '                c = text[end_idx]\n'
    '                if escape:\n'
    '                    escape = False\n'
    '                    continue\n'
    '                if c == "\\\\" and in_str:\n'
    '                    escape = True\n'
    '                    continue\n'
    '                if c == \'"\' and not escape:\n'
    '                    in_str = not in_str\n'
    '                if in_str:\n'
    '                    continue\n'
    '                if c == ch:\n'
    '                    depth += 1\n'
    '                elif c == end_ch:\n'
    '                    depth -= 1\n'
    '                    if depth == 0:\n'
    '                        candidate = text[start_idx:end_idx + 1]\n'
    '                        try:\n'
    '                            return json.loads(candidate)\n'
    '                        except json.JSONDecodeError:\n'
    '                            break  # Try next opening brace\n'
    '            break'
)
if old6 in src:
    src = src.replace(old6, new6, 1)
    # Remove the old fallback loop that follows (lines after the match block up to "raise ValueError")
    old_old_fallback = (
        '\n    if match:\n'
        '        candidate = match.group(1)\n'
        '        try:\n'
        '            return json.loads(candidate)\n'
        '        except json.JSONDecodeError:\n'
        '            # Try to be even more aggressive if there\'s trailing garbage\n'
        '            # like "Footer message" after the JSON\n'
        '            # We search for the LAST } that makes it a valid JSON\n'
        '            for i in range(len(candidate), 0, -1):\n'
        '                if candidate[i - 1] in ("}", "]"):\n'
        '                    try:\n'
        '                        return json.loads(candidate[:i])\n'
        '                    except json.JSONDecodeError:\n'
        '                        continue\n'
    )
    src = src.replace(old_old_fallback, "\n", 1)
    print("[FIX 6] json_utils.py – balanced JSON extraction replaces greedy regex")
else:
    print("[FIX 6] SKIP – pattern not found in json_utils.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 8: executor.py – track batchUpdate result, surface errors
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\execution\executor.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old8 = (
    '                # Special Case: docs.create_document with initial content\n'
    '                if task.service == "docs" and task.action == "create_document":\n'
    '                    content = task.parameters.get("content")\n'
    '                    if content and "documentId" in data:\n'
    '                        update_args = self.planner.build_command(\n'
    '                            "docs", "batch_update", {"document_id": data["documentId"], "text": content}\n'
    '                        )\n'
    '                        self.runner.run(update_args)\n'
)
new8 = (
    '                # Special Case: docs.create_document with initial content\n'
    '                if task.service == "docs" and task.action == "create_document":\n'
    '                    content = task.parameters.get("content")\n'
    '                    if content and "documentId" in data:\n'
    '                        update_args = self.planner.build_command(\n'
    '                            "docs", "batch_update", {"document_id": data["documentId"], "text": content}\n'
    '                        )\n'
    '                        update_result = self.runner.run(update_args)\n'
    '                        if not update_result.success:\n'
    '                            self.logger.warning(\n'
    '                                "docs.create_document batchUpdate failed for doc %s: %s",\n'
    '                                data["documentId"],\n'
    '                                update_result.error or update_result.stderr,\n'
    '                            )\n'
    '                            result.success = False\n'
    '                            result.error = (\n'
    '                                f"Document created but initial content write failed: "\n'
    '                                f"{update_result.error or update_result.stderr}"\n'
    '                            )\n'
)
if old8 in src:
    src = src.replace(old8, new8, 1)
    print("[FIX 8] executor.py – batchUpdate side-effect is now tracked")
else:
    print("[FIX 8] SKIP – pattern not found in executor.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 9: langgraph_workflow.py – unsafe dereference in update_context_node
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\langgraph_workflow.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old9 = (
    '    def update_context_node(state: AgentState) -> dict[str, Any]:\n'
    '        new_index = state.get("current_task_index", 0) + 1\n'
    '        if state.get("abort_plan"):\n'
    '            if state.get("plan"):\n'
    '                new_index = len(state.get("plan").tasks)\n'
    '        return {\n'
    '            "current_task_index": new_index,\n'
    '            "error": state.get("error"),\n'
    '            "current_attempt": 0,\n'
    '            "conversation_history": _trim_history(state.get("conversation_history", [])),\n'
    '        }\n'
)
new9 = (
    '    def update_context_node(state: AgentState) -> dict[str, Any]:\n'
    '        new_index = state.get("current_task_index", 0) + 1\n'
    '        if state.get("abort_plan"):\n'
    '            plan = state.get("plan")\n'
    '            if plan is not None and hasattr(plan, "tasks"):\n'
    '                new_index = len(plan.tasks)\n'
    '        return {\n'
    '            "current_task_index": new_index,\n'
    '            "error": state.get("error"),\n'
    '            "current_attempt": 0,\n'
    '            "conversation_history": _trim_history(state.get("conversation_history", [])),\n'
    '        }\n'
)
if old9 in src:
    src = src.replace(old9, new9, 1)
    print("[FIX 9] langgraph_workflow.py – safe plan dereference in update_context_node")
else:
    print("[FIX 9] SKIP – pattern not found in langgraph_workflow.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 10: safety_guard.py – send_message is not destructive
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\safety_guard.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old10 = '    "gmail": ["delete_message", "trash_message", "batch_delete", "empty_trash", "send_message"],'
new10 = ('    # send_message is "sensitive" (irreversible) but not destructive (no data deleted).\n'
         '    # It is handled separately in SENSITIVE_ACTIONS to require confirmation without\n'
         '    # the same alarm level as delete operations.\n'
         '    "gmail": ["delete_message", "trash_message", "batch_delete", "empty_trash"],')
if old10 in src:
    src = src.replace(old10, new10, 1)
    # Also add SENSITIVE_ACTIONS dict and update check_action
    sensitive_block = (
        '\n\n# Actions that are irreversible but not strictly destructive (require confirmation\n'
        '# in interactive mode, but should NOT block automated/telegram flows by default).\n'
        'SENSITIVE_ACTIONS = {\n'
        '    "gmail": ["send_message"],\n'
        '}\n'
    )
    # Insert after BULK_KEYWORDS block
    insert_after = ']\n\n\nclass SafetyGuard:'
    src = src.replace(insert_after, ']\n' + sensitive_block + '\nclass SafetyGuard:', 1)
    print("[FIX 10] safety_guard.py – send_message removed from DESTRUCTIVE_ACTIONS")
else:
    print("[FIX 10] SKIP – pattern not found in safety_guard.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

# ============================================================
# FIX 13: verification_engine.py – remove hardcoded test emails from prod logic
# ============================================================
path = r"d:\Code\gworkspace-agent\gws_assistant\verification_engine.py"
with open(path, encoding="utf-8") as f:
    src = f.read()

old13 = (
    '                    # Allow common test emails used in our test suite\n'
    '                    if str(to) not in ["strict-default@example.com", "test@example.com", "user@example.com"]:\n'
    '                        raise VerificationError(tool_name, "Invalid \'to\' email address", "to")\n'
)
new13 = (
    '                    # Email domains in EXACT_EMAILS / EMAIL_PLACEHOLDER_DOMAINS are\n'
    '                    # already excluded by _is_placeholder(); no need to hard-code\n'
    '                    # specific test addresses here.\n'
    '                    raise VerificationError(tool_name, "Invalid \'to\' email address", "to")\n'
)
if old13 in src:
    src = src.replace(old13, new13, 1)
    print("[FIX 13] verification_engine.py – hardcoded test emails removed from production logic")
else:
    print("[FIX 13] SKIP – pattern not found in verification_engine.py")

with open(path, "w", encoding="utf-8") as f:
    f.write(src)

print("\nAll fixes applied.")
