import logging

from gws_assistant.tools.code_execution import execute_generated_code

logger = logging.getLogger(__name__)


def test_sort_tools_by_price():
    tools = [("Cursor", 20), ("GitHub Copilot", 10), ("Tabnine", 12)]
    logger.info(f"Sorting tools by price: {tools}")
    code = f"tools = {tools}\nresult = sorted(tools, key=lambda x: x[1])"

    result = execute_generated_code(code)

    if not result["success"]:
        logger.error(f"Sorting operation failed: {result['error']}")
    else:
        logger.info(f"Sorting result: {result['output']['parsed_value']}")

    assert result["success"] is True
    assert result["output"]["parsed_value"] == [("GitHub Copilot", 10), ("Tabnine", 12), ("Cursor", 20)]
