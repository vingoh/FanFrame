import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tool.builtins import register_builtin_tools
from tool.tool_executor import ToolExecutor


def _exec(executor: ToolExecutor, name: str, args: dict, call_id: str = "t1"):
    return executor.execute_tool_call(
        {"name": name, "args": json.dumps(args, ensure_ascii=False), "call_id": call_id}
    )


def test_register_builtin_tools_loads_four_tools():
    executor = ToolExecutor()
    names = register_builtin_tools(executor)
    assert set(names) == {
        "GetCurrentTime",
        "EvaluateMath",
        "TruncateText",
        "FormatJson",
    }


def test_get_current_time_iso_utc():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "GetCurrentTime", {"timezone": "UTC", "format": "iso"})
    assert r.ok is True
    assert r.result
    assert "T" in r.result or "+" in r.result or r.result.endswith("Z") or "UTC" in r.result


def test_get_current_time_unix():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "GetCurrentTime", {"format": "unix"})
    assert r.ok is True
    assert r.result and r.result.isdigit()


def test_get_current_time_bad_timezone():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "GetCurrentTime", {"timezone": "NotAReal/Zone"})
    assert r.ok is True
    assert "错误" in (r.result or "")


def test_get_current_time_bad_format():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "GetCurrentTime", {"format": "nope"})
    assert r.ok is True
    assert "错误" in (r.result or "")


def test_evaluate_math_basic():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "EvaluateMath", {"expression": "(1 + 2) * 3 - 4 / 2"})
    assert r.ok is True
    assert r.result == "7"


def test_evaluate_math_float():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "EvaluateMath", {"expression": "3 / 2"})
    assert r.ok is True
    assert r.result == "1.5"


def test_evaluate_math_division_by_zero():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "EvaluateMath", {"expression": "1/0"})
    assert r.ok is True
    assert "除数" in (r.result or "")


def test_evaluate_math_empty_and_unsafe():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "EvaluateMath", {"expression": "   "})
    assert r.ok is True
    assert "空" in (r.result or "")

    r2 = _exec(executor, "EvaluateMath", {"expression": "__import__('os')"})
    assert r2.ok is True
    assert "错误" in (r2.result or "")


def test_truncate_text_not_truncated():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "TruncateText", {"text": "abc", "max_chars": 10})
    assert r.ok is True
    assert "abc" in (r.result or "")
    assert "truncated=false" in (r.result or "")


def test_truncate_text_truncated():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "TruncateText", {"text": "abcdef", "max_chars": 3})
    assert r.ok is True
    assert r.result.startswith("abc\n---")
    assert "truncated=true" in r.result


def test_truncate_text_negative_max_chars():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "TruncateText", {"text": "x", "max_chars": -1})
    assert r.ok is True
    assert "错误" in (r.result or "")


def test_format_json_pretty():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "FormatJson", {"text": '{"a":1}', "indent": 2})
    assert r.ok is True
    assert '"a"' in (r.result or "")
    assert (r.result or "").strip().startswith("{")


def test_format_json_invalid():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "FormatJson", {"text": "not json"})
    assert r.ok is True
    assert "错误" in (r.result or "")


def test_format_json_omit_indent_uses_default():
    executor = ToolExecutor()
    register_builtin_tools(executor)
    r = _exec(executor, "FormatJson", {"text": "[1]"})
    assert r.ok is True
    assert re.search(r"\[\s*1\s*\]", r.result or "")
