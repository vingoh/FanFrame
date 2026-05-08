import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from tool.tool_manifest import validate_and_iterate_tools


@dataclass
class ToolSpec:
    """工具定义（声明层）"""

    name: str
    description: str
    func: Callable[..., Any]
    schema: Optional[Dict[str, Any]] = None


@dataclass
class ToolExecutionResult:
    """统一工具执行结果（实例层）"""

    call_id: str
    name: str
    ok: bool
    result: Any = None
    error_type: str = ""
    error_message: str = ""


class ToolExecutor:
    """工具执行器：管理工具注册、参数校验与统一协议执行。"""

    def __init__(self):
        self.tools: Dict[str, ToolSpec] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        schema: Optional[Dict[str, Any]] = None,
    ):
        """注册工具，支持可选 schema。"""
        if name in self.tools:
            print(f"警告:工具 '{name}' 已存在，将被覆盖。")
        self.tools[name] = ToolSpec(name=name, description=description, func=func, schema=schema)
        print(f"工具 '{name}' 已注册。")

    def register_from_manifest(self, path: Union[str, Path]) -> List[str]:
        """
        从 JSON 清单文件批量注册工具。

        格式约定见 tool.tool_manifest 模块文档（version、tools、handler、schema）。
        任一条目校验失败或 handler 不可解析则整文件失败（抛出异常）。
        """
        manifest_path = Path(path)
        with manifest_path.open(encoding="utf-8") as f:
            data = json.load(f)
        entries = validate_and_iterate_tools(data)
        registered: List[str] = []
        for name, description, func, schema in entries:
            self.register_tool(name, description, func, schema)
            registered.append(name)
        return registered

    def get_tool(self, name: str) -> Optional[Callable[..., Any]]:
        """兼容接口：按名称获取执行函数。"""
        spec = self.tools.get(name)
        if not spec:
            return None
        return spec.func

    def get_tool_spec(self, name: str) -> Optional[ToolSpec]:
        """按名称获取工具定义。"""
        return self.tools.get(name)

    def get_available_tools(self) -> str:
        """获取可用工具的格式化描述。"""
        return "\n".join([f"- {name}: {spec.description}" for name, spec in self.tools.items()])

    def execute_tool_call(self, tool_call: Union[Dict[str, Any], Any]) -> ToolExecutionResult:
        """
        按统一协议执行工具：
        - 输入: {name, args, call_id}
        - 输出: ToolExecutionResult（含 call_id）
        """
        name = self._get_field(tool_call, "name")
        args_raw = self._get_field(tool_call, "args")
        call_id = self._get_field(tool_call, "call_id") or ""

        spec = self.get_tool_spec(name)
        # 工具不存在    
        if not spec:
            return ToolExecutionResult(
                call_id=call_id,
                name=name,
                ok=False,
                error_type="tool_not_found",
                error_message=f"未找到名为 '{name}' 的工具。",
            )
        # 参数解析
        parsed_args = self._parse_args(args_raw)
        if parsed_args is None:
            return ToolExecutionResult(
                call_id=call_id,
                name=name,
                ok=False,
                error_type="schema_validation_error",
                error_message="工具参数必须是 JSON 对象字符串或 dict。",
            )
        # 参数校验
        valid, error = self._validate_args(parsed_args, spec.schema)
        if not valid:
            return ToolExecutionResult(
                call_id=call_id,
                name=name,
                ok=False,
                error_type="schema_validation_error",
                error_message=error,
            )
        # 工具执行
        try:
            result = spec.func(**parsed_args)
            return ToolExecutionResult(call_id=call_id, name=name, ok=True, result=result)
        except Exception as exc:
            return ToolExecutionResult(
                call_id=call_id,
                name=name,
                ok=False,
                error_type="tool_execution_error",
                error_message=str(exc),
            )

    @staticmethod
    def _get_field(obj: Union[Dict[str, Any], Any], key: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(key, "")
        return getattr(obj, key, "")

    @staticmethod
    def _parse_args(args_raw: Any) -> Optional[Dict[str, Any]]:
        if args_raw in ("", None):
            return {}
        if isinstance(args_raw, dict):
            return args_raw
        if isinstance(args_raw, str):
            try:
                loaded = json.loads(args_raw)
            except json.JSONDecodeError:
                return None
            if not isinstance(loaded, dict):
                return None
            return loaded
        return None

    @staticmethod
    def _validate_args(
        args_dict: Dict[str, Any],
        schema: Optional[Dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        最小 JSON Schema 子集校验：
        - type=object
        - required
        - properties.<field>.type in [string, number, integer, boolean, object, array]
        """
        if not schema:
            return True, ""
        if schema.get("type") not in (None, "object"):
            return False, "schema 顶层仅支持 type=object。"

        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in args_dict:
                return False, f"缺少必填参数: {field}"

        properties = schema.get("properties", {})
        for field_name, field_schema in properties.items():
            if field_name not in args_dict:
                continue
            expected_type = field_schema.get("type")
            if not expected_type:
                continue
            if not ToolExecutor._is_type_match(args_dict[field_name], expected_type):
                return False, f"参数类型错误: {field_name} 应为 {expected_type}"
        return True, ""

    @staticmethod
    def _is_type_match(value: Any, expected_type: str) -> bool:
        type_mapping = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "object": dict,
            "array": list,
        }
        expected = type_mapping.get(expected_type)
        if expected is None:
            return True
        if expected_type == "integer" and isinstance(value, bool):
            return False
        if expected_type == "number" and isinstance(value, bool):
            return False
        return isinstance(value, expected)
