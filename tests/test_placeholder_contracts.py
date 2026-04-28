def test_drive_summary_values_alias_resolves():
    context = {"drive_summary_rows": [["file.pdf", "application/pdf", "http://link"]]}
    # simulate resolver lookup for $drive_summary_values
    from gws_assistant.execution.resolver import LEGACY_PLACEHOLDER_MAP
    canonical = LEGACY_PLACEHOLDER_MAP.get("$drive_summary_values")
    assert canonical == "drive_summary_rows"
    assert context.get(canonical) == context["drive_summary_rows"]

def test_last_code_result_maps_to_parsed_value():
    from gws_assistant.execution.resolver import LEGACY_PLACEHOLDER_MAP
    assert LEGACY_PLACEHOLDER_MAP.get("$last_code_result") == "code_parsed_value"
    assert LEGACY_PLACEHOLDER_MAP.get("$last_code_stdout") == "code_output"

def test_gmail_summary_values_is_independent_copy():
    from gws_assistant.execution.context_updater import ContextUpdaterMixin
    updater = ContextUpdaterMixin()
    context = {}
    data = {"messages": [{"id": "msg1", "threadId": "t1"}]}
    updater._update_context_from_result(data, context)
    original = context["gmail_summary_rows"]
    context["gmail_summary_rows"].append(["mutated"])
    assert context["gmail_summary_values"] == original, \
        "gmail_summary_values should be independent copy not same list object"
