from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
from .message import Message
from .llm import BaseLLM
from .config import Config
from tool.tool_executor import ToolExecutor

class Agent(ABC):
    """Agent基类"""
    
    def __init__(
        self,
        name: str,
        llm: BaseLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_executor: Optional[ToolExecutor] = None
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self.tool_executor = tool_executor or ToolExecutor()
        self._history: list[Message] = []
    
    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """运行Agent"""
        pass
    
    def add_message(self, message: Message):
        """添加消息到历史记录"""
        self._history.append(message)
    
    def clear_history(self):
        """清空历史记录"""
        self._history.clear()
    
    def get_history(self) -> list[Message]:
        """获取历史记录"""
        return self._history.copy()

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

    def get_available_tools(self) -> str:
        """获取当前Agent可用工具列表"""
        return self.tool_executor.get_available_tools()

    def execute_tool(self, name: str, tool_input: Any = None, **kwargs) -> Any:
        """执行工具；默认将tool_input作为首参数传给工具函数"""
        tool_function = self.tool_executor.get_tool(name)
        if not tool_function:
            raise ValueError(f"未找到名为 '{name}' 的工具。")

        if tool_input is None:
            return tool_function(**kwargs) if kwargs else tool_function()
        return tool_function(tool_input, **kwargs)

    def execute_tool_call(self, tool_call: Any) -> Any:
        """按统一协议执行工具调用（name + args + call_id）。"""
        return self.tool_executor.execute_tool_call(tool_call)
    
    def __str__(self) -> str:
        return f"Agent(name={self.name}, provider={self.llm.provider})"
