import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tool.tool_executor import ToolExecutor


def test_register_and_execute_tool_call_success():
    executor = ToolExecutor()

    def echo(query: str) -> str:
        return f"echo:{query}"

    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    executor.register_tool(name="Search", description="search", func=echo, schema=schema)

    result = executor.execute_tool_call(
        {"name": "Search", "args": '{"query":"nvidia"}', "call_id": "call_1"}
    )

    assert result.ok is True
    assert result.call_id == "call_1"
    assert result.name == "Search"
    assert result.result == "echo:nvidia"


def test_execute_tool_call_missing_required_argument():
    executor = ToolExecutor()

    def echo(query: str) -> str:
        return query

    schema = {"type": "object", "required": ["query"]}
    executor.register_tool(name="Search", description="search", func=echo, schema=schema)

    result = executor.execute_tool_call(
        {"name": "Search", "args": "{}", "call_id": "call_missing"}
    )

    assert result.ok is False
    assert result.error_type == "schema_validation_error"
    assert "缺少必填参数" in result.error_message
    assert result.call_id == "call_missing"


def test_execute_tool_call_invalid_argument_type():
    executor = ToolExecutor()

    def echo(query: str) -> str:
        return query

    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    executor.register_tool(name="Search", description="search", func=echo, schema=schema)

    result = executor.execute_tool_call(
        {"name": "Search", "args": '{"query":123}', "call_id": "call_bad_type"}
    )

    assert result.ok is False
    assert result.error_type == "schema_validation_error"
    assert "参数类型错误" in result.error_message


def test_execute_tool_call_tool_not_found():
    executor = ToolExecutor()
    result = executor.execute_tool_call({"name": "Missing", "args": "{}", "call_id": "call_404"})

    assert result.ok is False
    assert result.error_type == "tool_not_found"
    assert result.call_id == "call_404"


def test_execute_tool_call_execution_error():
    executor = ToolExecutor()

    def boom() -> str:
        raise RuntimeError("boom")

    executor.register_tool(name="Crash", description="crash", func=boom, schema={"type": "object"})
    result = executor.execute_tool_call({"name": "Crash", "args": "{}", "call_id": "call_err"})

    assert result.ok is False
    assert result.error_type == "tool_execution_error"
    assert "boom" in result.error_message


def test_execute_tool_call_accepts_object_shape():
    executor = ToolExecutor()

    def add(a: int, b: int) -> int:
        return a + b

    schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
        "required": ["a", "b"],
    }
    executor.register_tool(name="Add", description="add", func=add, schema=schema)

    tool_call = SimpleNamespace(name="Add", args='{"a":1,"b":2}', call_id="call_obj")
    result = executor.execute_tool_call(tool_call)

    assert result.ok is True
    assert result.result == 3
    assert result.call_id == "call_obj"
