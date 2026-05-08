import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tool.tool_executor import ToolExecutor
from tool.tool_manifest import resolve_handler, validate_and_iterate_tools


def test_resolve_handler_valid():
    fn = resolve_handler("tool.manifest_stub:echo_stub")
    assert fn("x") == "stub:x"


def test_resolve_handler_invalid_format():
    with pytest.raises(ValueError, match="handler 格式无效"):
        resolve_handler("nocolon")


def test_validate_and_iterate_tools_success():
    data = {
        "version": 1,
        "tools": [
            {
                "name": "Echo",
                "description": "d",
                "handler": "tool.manifest_stub:echo_stub",
                "schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            }
        ],
    }
    entries = validate_and_iterate_tools(data)
    assert len(entries) == 1
    name, desc, func, schema = entries[0]
    assert name == "Echo"
    assert desc == "d"
    assert schema is not None
    assert func("a") == "stub:a"


def test_validate_duplicate_name_in_manifest():
    data = {
        "version": 1,
        "tools": [
            {"name": "A", "description": "1", "handler": "tool.manifest_stub:echo_stub"},
            {"name": "A", "description": "2", "handler": "tool.manifest_stub:echo_stub"},
        ],
    }
    with pytest.raises(ValueError, match="重复"):
        validate_and_iterate_tools(data)


def test_validate_unsupported_version():
    with pytest.raises(ValueError, match="version"):
        validate_and_iterate_tools({"version": 2, "tools": []})


def test_validate_tools_empty():
    with pytest.raises(ValueError):
        validate_and_iterate_tools({"version": 1, "tools": []})


def test_register_from_manifest_end_to_end(tmp_path):
    manifest = {
        "version": 1,
        "tools": [
            {
                "name": "Echo",
                "description": "echo",
                "handler": "tool.manifest_stub:echo_stub",
                "schema": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                    "required": ["message"],
                },
            }
        ],
    }
    p = tmp_path / "tools.manifest.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")

    executor = ToolExecutor()
    names = executor.register_from_manifest(p)
    assert names == ["Echo"]

    result = executor.execute_tool_call(
        {"name": "Echo", "args": '{"message":"hello"}', "call_id": "c1"}
    )
    assert result.ok is True
    assert result.result == "stub:hello"
    assert result.call_id == "c1"


def test_register_from_manifest_bad_handler_fails(tmp_path):
    manifest = {
        "version": 1,
        "tools": [
            {
                "name": "Bad",
                "description": "x",
                "handler": "tool.manifest_stub:nonexistent_func",
            }
        ],
    }
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(manifest), encoding="utf-8")

    executor = ToolExecutor()
    with pytest.raises((ValueError, AttributeError)):
        executor.register_from_manifest(p)
