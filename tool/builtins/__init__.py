"""内置工具包：时间、安全算术、文本与 JSON 处理。通过 manifest 注册到 ToolExecutor。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from tool.tool_executor import ToolExecutor

BUILTIN_MANIFEST_PATH = Path(__file__).resolve().parent / "builtin.manifest.json"


def register_builtin_tools(executor: "ToolExecutor") -> List[str]:
    """从同目录下的 builtin.manifest.json 加载并注册全部内置工具。"""
    return executor.register_from_manifest(BUILTIN_MANIFEST_PATH)
