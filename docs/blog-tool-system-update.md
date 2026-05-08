# FanFrame 工具系统演进：从「能跑」到「可校验、可追踪、可从文件加载」

本文基于当前仓库中与 tool 相关的改动，说明设计理念与用法。对应 roadmap 中 Tool System 的 P0 方向：**工具注册与调用**、**参数 schema 校验**、**统一 tool call 协议（name + args + call_id）**，以及后续的 **JSON 清单手动加载**。

---

## 背景：为什么要分层

工具在 Agent 框架里承担两件事：

1. **声明**：这个工具叫什么、做什么、参数长什么样（给 LLM 的 `tools` 列表与人类阅读）。
2. **执行**：模型在一次对话里发出了具体调用请求，如何把这次请求安全地变成函数调用，并把结果和 **调用 id** 对齐，便于 trace。

因此代码里把「定义」和「一次调用」拆开：

- **ToolSpec（声明层）**：`name`、`description`、实现函数 `func`、可选 `schema`（参数契约）。
- **ToolCall（协议层）**：与 `core/llm.py` 中解析出的结构一致，即 `name` + `args` + `call_id`；`args` 在链路上多为 JSON 字符串，执行前会解析为 `dict` 再按 schema 校验。
- **ToolExecutionResult（结果层）**：无论成功失败，都带上 `call_id`，并区分 `error_type`，方便编排层和可观测性统一处理。

`ToolSpec` 与 `ToolExecutionResult` 使用 `dataclass` 表达纯数据；与 LLM 边界相关的结构仍可在 `core/llm.py` 中沿用 Pydantic `BaseModel`（如 `ToolCall`），这是刻意为之：**协议解析用 Pydantic，执行器内部值对象用 dataclass**，减少依赖与样板之间的扯皮。

---

## 核心设计一：`ToolExecutor` 与统一执行协议

`ToolExecutor` 负责维护 `name -> ToolSpec` 的注册表，并提供 **`execute_tool_call`**：入参可以是 dict 或带同名属性的对象（兼容 LLM 解析结果）。

执行顺序可以概括为：解析字段 → 查找工具 → 解析 `args` → schema 校验 → `func(**parsed_args)` → 封装结果。

```82:133:tool/tool_executor.py
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
```

**错误类型约定**（便于上游统一分支）：

| `error_type` | 含义 |
|--------------|------|
| `tool_not_found` | 未注册的工具名 |
| `schema_validation_error` | `args` 不是合法 JSON 对象，或不符合 schema |
| `tool_execution_error` | 校验通过后，工具函数抛出的异常 |

这样编排层可以把「模型胡说八道」与「工具实现 bug」分开统计。

---

## 核心设计二：最小 JSON Schema 子集

完整 JSON Schema 很重；当前实现只支持 **`type=object`、`required`、`properties.*.type`** 这一子集，与 roadmap 里「先做 P0、渐进增强」一致。实现见 `_validate_args` 与 `_is_type_match`。

```157:187:tool/tool_executor.py
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
```

注册工具时传入同一套 `schema`，即可在执行前挡住大部分非法调用；不显式传 `schema` 则跳过校验（兼容旧代码路径）。

---

## 使用方法一：在代码里注册（含 schema）

`register_tool` 现在支持可选 `schema`，`Agent` 层已转发到 `ToolExecutor`：

```43:53:core/agent.py
    def register_tool(
        self,
        name: str,
        description: str,
        func: Callable[..., Any],
        schema: Optional[Dict[str, Any]] = None,
    ):
        """注册工具到当前Agent工具箱"""
        self.tool_executor.register_tool(
            name=name, description=description, func=func, schema=schema
        )
```

典型用法：定义与 OpenAI `tools[].function.parameters` 对齐的 schema，保证「模型看到的参数」和「执行器校验的参数」一致。

执行统一协议调用时，使用 **`execute_tool_call`**（Agent 上同样委托给 executor）：

```python
result = agent.execute_tool_call({
    "name": "Search",
    "args": '{"query": "今日天气"}',
    "call_id": "call_abc",
})
# result.ok / result.result / result.error_type / result.call_id
```

仍保留的 **`execute_tool(name, tool_input, ...)`** 适合脚本式直接调函数；与 LLM 闭环对接时优先 **`execute_tool_call`**，以便带上 `call_id` 和结构化错误。

---

## 使用方法二：从 JSON 清单文件批量注册

为满足「配置与代码分离、但仍由开发者显式加载」的需求，增加了 **manifest（版本 1）**：单一 UTF-8 JSON 文件，顶层 `version` + `tools` 数组；每条包含 `name`、`description`、`handler`、`schema`（可选）。

**`handler` 格式**：`"<module_path>:<attribute>"`，例如 `tool.search_tool:search`。通过 `importlib.import_module` 与 `getattr` 解析，**不在文件里写任意代码字符串、不走 `exec`**，安全边界更清晰。

解析逻辑见 `tool_manifest.py`：

```30:46:tool/tool_manifest.py
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
```

在 `ToolExecutor` 上一次性加载：

```50:65:tool/tool_executor.py
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
```

清单内 **`name` 必须唯一**；版本号暂只支持 `1`。若某条 `handler` 无法导入或不可调用，**整文件失败**（抛出异常），避免「默默少注册一半工具」导致线上难排查。项目中提供了仅供测试/示例的桩模块 `tool.manifest_stub`（如 `echo_stub`），单元测试里用临时文件写入最小 manifest 做端到端验证。

**示例 manifest（节选）**：

```json
{
  "version": 1,
  "tools": [
    {
      "name": "Search",
      "description": "网页搜索。",
      "handler": "tool.search_tool:search",
      "schema": {
        "type": "object",
        "properties": { "query": { "type": "string" } },
        "required": ["query"]
      }
    }
  ]
}
```

---

## 与 LLM 侧的衔接（简要）

`core/llm.py` 将流式/非流式响应统一解析为带 `ToolCall(name, args, call_id)` 的结构；执行层只要消费同一字段名，即可与 **`execute_tool_call`** 对接。后续在 Orchestrator 里把工具返回写入 `role=tool` 消息时，务必使用相同的 `call_id`，trace 才能闭环。

---

## 测试与回归

- `tests/test_tool_executor.py`：注册、schema 成功/失败、`call_id` 透传等。
- `tests/test_tool_manifest.py`：manifest 校验、`resolve_handler`、`register_from_manifest` 端到端。

编写功能或调整校验规则时，建议同时跑：`pytest tests/test_tool_executor.py tests/test_tool_manifest.py tests/test_llm.py`。

---

## 小结

| 能力 | 说明 |
|------|------|
| 声明与执行分离 | `ToolSpec` + 统一 `ToolCall` 协议 |
| 参数契约 | 可选 JSON Schema 子集，执行前校验 |
| 可追踪 | `ToolExecutionResult` 始终带 `call_id` 与标准 `error_type` |
| 配置化注册 | `register_from_manifest` + `module:attr` handler |

这套设计优先保证 **主链路稳定、错误可分类、行为可测试**；目录自动扫描、权限分级、重试策略等可放在后续里程碑（roadmap P1/P2）逐步加。
