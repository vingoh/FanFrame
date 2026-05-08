"""供 manifest 单测与示例使用的桩函数（可被 handler `tool.manifest_stub:echo_stub` 引用）。"""


def echo_stub(message: str) -> str:
    return f"stub:{message}"
