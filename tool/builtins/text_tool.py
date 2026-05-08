"""内置工具：文本截断与 JSON 格式化。"""

from __future__ import annotations

import json


def truncate_text(text: str, max_chars: int) -> str:
    """
    截断文本至最多 max_chars 个字符（按 Unicode 码位长度），并附长度与是否截断说明。
    """
    if max_chars < 0:
        return "错误: max_chars 不能为负数。"

    body = text or ""
    n = len(body)
    if n <= max_chars:
        return f"{body}\n---\nlength={n}, truncated=false, max_chars={max_chars}"

    return (
        f"{body[:max_chars]}\n---\n"
        f"length={n}, truncated=true, max_chars={max_chars}"
    )


def format_json(text: str, indent: int = 2) -> str:
    """解析 JSON 字符串并以缩进美化输出；非法 JSON 返回错误说明。"""
    raw = text if text is not None else ""
    ind = 2 if indent is None else indent
    if ind < 0:
        ind = 0
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        return f"错误: JSON 无效: {e}"

    return json.dumps(obj, ensure_ascii=False, indent=ind)
