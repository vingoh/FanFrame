"""内置工具：当前时间（ISO 8601 或 Unix 秒）。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def get_current_time(timezone: str = "UTC", format: str = "iso") -> str:
    """
    返回指定时区的当前时间。
    format: \"iso\" 为 ISO 8601 字符串；\"unix\" 为 Unix 时间戳（整数秒字符串）。
    """
    tz_name = (timezone or "").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        return f"错误: 无效的时区名称: {timezone!r}。"

    now = datetime.now(tz)
    fmt = (format or "iso").strip().lower()
    if fmt == "unix":
        return str(int(now.timestamp()))
    if fmt == "iso":
        return now.isoformat()
    return f"错误: format 必须是 iso 或 unix，当前为 {format!r}。"
