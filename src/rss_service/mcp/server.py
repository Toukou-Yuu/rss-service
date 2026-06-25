import json
import sys
from collections.abc import Callable
from typing import Any, cast

from rss_service.mcp.tools import TOOLS


def run_stdio_server() -> None:
    for line in sys.stdin:
        request = json.loads(line)
        tool_name = request["tool"]
        arguments = request.get("arguments", {})
        result = call_tool(tool_name, arguments)
        sys.stdout.write(json.dumps({"result": result}, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    if tool_name not in TOOLS:
        raise KeyError(tool_name)
    tool = cast(Callable[..., Any], TOOLS[tool_name])
    return tool(**arguments)
