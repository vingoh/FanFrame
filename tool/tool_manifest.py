"""
工具清单（manifest）文件约定 — 与 JSON 内容一一对应。

文件为单一 UTF-8 JSON 对象，当前仅支持 version=1。

顶层:
  version: int，必填，当前仅允许 1
  tools: list，必填，工具条目

tools[] 每条:
  name: str，必填，在文件内必须唯一
  description: str，必填
  handler: str，必填，格式 \"<module_path>:<attribute>\"，见 resolve_handler
  schema: object | null，选填；与 ToolExecutor 内 JSON Schema 子集一致

示例见 register_from_manifest 的调用方或 tests。
"""

from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, List, Tuple

# 与 manifest 顶层 version 字段对齐
MANIFEST_VERSION = 1

REQUIRED_TOOL_KEYS = ("name", "description", "handler")


def resolve_handler(handler: str) -> Callable[..., Any]:
    """
    将 \"module.sub:func_name\" 解析为可调用对象。
    不做沙箱外执行，仅 import + getattr。
    """
    if ":" not in handler:
        raise ValueError(f"handler 格式无效，应为 'module:attr'：{handler!r}")
    mod_path, attr = handler.split(":", 1)
    if not mod_path or not attr:
        raise ValueError(f"handler 格式无效：{handler!r}")
    module = importlib.import_module(mod_path)
    obj = getattr(module, attr, None)
    if obj is None:
        raise ValueError(f"模块 {mod_path!r} 中不存在属性 {attr!r}")
    if not callable(obj):
        raise ValueError(f"{handler!r} 指向的对象不可调用")
    return obj


def _parse_manifest_dict(data: Any) -> List[Dict[str, Any]]:
    """校验顶层结构，返回 tools 列表（未解析 handler）。"""
    if not isinstance(data, dict):
        raise ValueError("清单根节点必须是 JSON object")
    version = data.get("version")
    if version != MANIFEST_VERSION:
        raise ValueError(
            f"不支持的 manifest version: {version!r}，当前仅支持 {MANIFEST_VERSION}"
        )
    tools = data.get("tools")
    if not isinstance(tools, list):
        raise ValueError("tools 字段必须是非空数组")
    if len(tools) == 0:
        raise ValueError("tools 必须至少包含一条工具定义")

    seen: set[str] = set()
    for i, item in enumerate(tools):
        if not isinstance(item, dict):
            raise ValueError(f"tools[{i}] 必须是 object")
        for key in REQUIRED_TOOL_KEYS:
            if key not in item:
                raise ValueError(f"tools[{i}] 缺少必填字段 {key!r}")
        name = item["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"tools[{i}].name 必须是非空字符串")
        if name in seen:
            raise ValueError(f"清单内工具名重复: {name!r}")
        seen.add(name)
        if not isinstance(item["description"], str):
            raise ValueError(f"tools[{i}].description 必须是字符串")
        if not isinstance(item["handler"], str) or not item["handler"].strip():
            raise ValueError(f"tools[{i}].handler 必须是非空字符串")
        schema = item.get("schema", None)
        if schema is not None and not isinstance(schema, dict):
            raise ValueError(f"tools[{i}].schema 必须是 object 或省略/null")

    return tools  # type: ignore[return-value]


def validate_and_iterate_tools(
    data: Any,
) -> List[Tuple[str, str, Callable[..., Any], Dict[str, Any] | None]]:
    """
    校验 manifest 并解析每个 handler。
    返回 [(name, description, func, schema_or_none), ...]
    任一 handler 解析失败则抛出 ValueError（整文件失败）。
    """
    raw_list = _parse_manifest_dict(data)
    out: List[Tuple[str, str, Callable[..., Any], Dict[str, Any] | None]] = []
    for item in raw_list:
        name = item["name"].strip()
        description = item["description"]
        handler_str = item["handler"].strip()
        schema = item.get("schema")
        if schema is not None and len(schema) == 0:
            schema = None
        func = resolve_handler(handler_str)
        schema_typed: Dict[str, Any] | None = schema if isinstance(schema, dict) else None
        out.append((name, description, func, schema_typed))
    return out
