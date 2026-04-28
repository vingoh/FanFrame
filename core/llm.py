import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Optional, Tuple, Any
from pydantic import BaseModel, Field

# 加载 .env 文件中的环境变量
load_dotenv()

class ToolCall(BaseModel):
    """统一工具调用结构"""

    name: str = ""
    args: str = ""
    call_id: str = ""


class UsageInfo(BaseModel):
    """统一token使用量结构"""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class LLMResponse(BaseModel):
    """统一LLM响应结构（流式/非流式）"""

    text: str = ""
    tool_calls: List[ToolCall] = Field(default_factory=list)
    finish_reason: Optional[str] = None
    usage: Optional[UsageInfo] = None
    raw: Optional[Dict[str, Any]] = None


class BaseLLM:
    """
    用于调用任何兼容OpenAI接口的服务，并默认使用流式响应。
    """
    def __init__(self, model: str = None, apiKey: str = None, baseUrl: str = None, timeout: int = None):
        """
        初始化客户端。优先使用传入参数，如果未提供，则从环境变量加载。
        """
        self.model = model or os.getenv("LLM_MODEL_ID")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        # 自动识别 provider，并按 provider 规则解析凭据
        self.provider = self._auto_detect_provider(apiKey, baseUrl)
        self.api_key, self.base_url = self._resolve_credentials(apiKey, baseUrl)

        if not all([self.model, self.api_key, self.base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=timeout)

    def think(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0,
        stream: bool = True,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
    ) -> LLMResponse:
        """
        调用大语言模型并返回统一结构化响应。
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "stream": stream,
            }
            if tools:
                request_kwargs["tools"] = tools
            if tool_choice is not None:
                request_kwargs["tool_choice"] = tool_choice

            response = self.client.chat.completions.create(**request_kwargs)

            print("✅ 大语言模型响应成功:")
            if stream:
                return self._parse_stream_response(response)
            return self._parse_non_stream_response(response)
        except Exception as e:
            raise RuntimeError(f"[LLM][ERROR] 调用LLM API时发生错误: {e}") from e

    def _parse_stream_response(self, stream_response: Any) -> LLMResponse:
        """解析流式响应为统一结构"""
        collected_content: List[str] = []
        tool_call_chunks: Dict[int, Dict[str, str]] = {}
        finish_reason: Optional[str] = None
        usage_info: Optional[UsageInfo] = None

        for chunk in stream_response:
            chunk_usage = self._extract_usage(chunk)
            if chunk_usage:
                usage_info = chunk_usage

            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue

            choice = choices[0]
            chunk_finish_reason = getattr(choice, "finish_reason", None)
            if chunk_finish_reason:
                finish_reason = chunk_finish_reason

            delta = getattr(choice, "delta", None)
            if not delta:
                continue

            content = getattr(delta, "content", "") or ""
            if content:
                print(content, end="", flush=True)
                collected_content.append(content)

            delta_tool_calls = getattr(delta, "tool_calls", None) or []
            for tc in delta_tool_calls:
                index = getattr(tc, "index", 0)
                entry = tool_call_chunks.setdefault(index, {"name": "", "args": "", "call_id": ""})
                call_id = getattr(tc, "id", None)
                if call_id:
                    entry["call_id"] = call_id

                function = getattr(tc, "function", None)
                if function:
                    name_part = getattr(function, "name", "") or ""
                    args_part = getattr(function, "arguments", "") or ""
                    if name_part:
                        entry["name"] = name_part
                    if args_part:
                        entry["args"] += args_part

        print()
        tool_calls = [
            ToolCall(name=item["name"], args=item["args"], call_id=item["call_id"])
            for _, item in sorted(tool_call_chunks.items(), key=lambda pair: pair[0])
        ]
        return LLMResponse(
            text="".join(collected_content),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage_info,
            raw=None,
        )

    def _parse_non_stream_response(self, response: Any) -> LLMResponse:
        """解析非流式响应为统一结构"""
        choices = getattr(response, "choices", None) or []
        if not choices:
            return LLMResponse(usage=self._extract_usage(response), raw=self._safe_dump(response))

        choice = choices[0]
        message = getattr(choice, "message", None)

        content = ""
        tool_calls: List[ToolCall] = []
        if message:
            content = getattr(message, "content", "") or ""
            raw_tool_calls = getattr(message, "tool_calls", None) or []
            for tc in raw_tool_calls:
                function = getattr(tc, "function", None)
                tool_calls.append(
                    ToolCall(
                        name=getattr(function, "name", "") if function else "",
                        args=getattr(function, "arguments", "") if function else "",
                        call_id=getattr(tc, "id", "") or "",
                    )
                )

        return LLMResponse(
            text=content,
            tool_calls=tool_calls,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=self._extract_usage(response),
            raw=self._safe_dump(response),
        )

    def _extract_usage(self, response_like: Any) -> Optional[UsageInfo]:
        """从响应对象提取 usage"""
        usage = getattr(response_like, "usage", None)
        if not usage:
            return None
        return UsageInfo(
            prompt_tokens=getattr(usage, "prompt_tokens", None),
            completion_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )

    def _safe_dump(self, response_like: Any) -> Optional[Dict[str, Any]]:
        """尽可能保留原始响应字典，失败则返回None"""
        model_dump = getattr(response_like, "model_dump", None)
        if callable(model_dump):
            try:
                return model_dump()
            except Exception:
                return None
        return None

    def _auto_detect_provider(self, api_key: Optional[str], base_url: Optional[str]) -> str:
        """
        自动检测LLM提供商
        """
        # 1. 检查特定提供商的环境变量 (最高优先级)
        if os.getenv("MODELSCOPE_API_KEY"): return "modelscope"
        if os.getenv("OPENAI_API_KEY"): return "openai"
        if os.getenv("ZHIPU_API_KEY"): return "zhipu"

        actual_api_key = api_key or os.getenv("LLM_API_KEY")
        actual_base_url = base_url or os.getenv("LLM_BASE_URL")

        # 2. 根据 base_url 判断
        if actual_base_url:
            base_url_lower = actual_base_url.lower()
            if "api-inference.modelscope.cn" in base_url_lower: return "modelscope"
            if "open.bigmodel.cn" in base_url_lower: return "zhipu"
            if "localhost" in base_url_lower or "127.0.0.1" in base_url_lower:
                if ":11434" in base_url_lower: return "ollama"
                if ":8000" in base_url_lower: return "vllm"
                return "local" # 其他本地端口

        # 3. 根据 API 密钥格式辅助判断
        if actual_api_key:
            if actual_api_key.startswith("ms-"): return "modelscope"

        # 4. 默认返回 'auto'，使用通用配置
        return "auto"

    def _resolve_credentials(self, api_key: Optional[str], base_url: Optional[str]) -> Tuple[str, str]:
        """根据provider解析API密钥和base_url"""
        if self.provider == "openai":
            resolved_api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1"
            return resolved_api_key, resolved_base_url

        if self.provider == "modelscope":
            resolved_api_key = api_key or os.getenv("MODELSCOPE_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = (
                base_url
                or os.getenv("LLM_BASE_URL")
                or "https://api-inference.modelscope.cn/v1"
            )
            return resolved_api_key, resolved_base_url

        if self.provider == "zhipu":
            resolved_api_key = api_key or os.getenv("ZHIPU_API_KEY") or os.getenv("LLM_API_KEY")
            resolved_base_url = base_url or os.getenv("LLM_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4"
            return resolved_api_key, resolved_base_url

        # 对本地/ollama/vllm/auto 场景，沿用通用配置
        resolved_api_key = api_key or os.getenv("LLM_API_KEY")
        resolved_base_url = base_url or os.getenv("LLM_BASE_URL")
        return resolved_api_key, resolved_base_url

# --- 客户端使用示例 ---
if __name__ == '__main__':
    try:
        llmClient = BaseLLM()
        
        exampleMessages = [
            {"role": "system", "content": "You are a helpful assistant. You can use a search tool to get the latest information."},
            {"role": "user", "content": "英伟达的最新gpu是什么"}
        ]
        exampleTools = [
            {
                "type": "function",
                "function": {
                    "name": "Search",
                    "description": "当你需要最新信息时，调用该工具执行网页搜索。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "搜索关键词"}
                        },
                        "required": ["query"],
                    },
                },
            }
        ]
        
        print("--- 第1轮调用LLM（允许工具调用） ---")
        response_data = llmClient.think(
            exampleMessages,
            stream=True,
            tools=exampleTools,
            tool_choice="auto",
        )
        print("\n\n--- 完整模型响应 ---")
        if response_data.text:
            print(response_data.text)
        else:
            print("[无文本内容，模型返回了工具调用请求]")
        print(f"finish_reason: {response_data.finish_reason}")
        print(f"tool_calls: {response_data.tool_calls}")
        print(f"usage: {response_data.usage}")

        if response_data.tool_calls:
            first_tool_call = response_data.tool_calls[0]
            print("\n--- 模拟执行工具并回填结果 ---")
            print(f"tool_name: {first_tool_call.name}")
            print(f"tool_args: {first_tool_call.args}")

            try:
                tool_args_obj = json.loads(first_tool_call.args) if first_tool_call.args else {}
            except json.JSONDecodeError:
                tool_args_obj = {"raw_args": first_tool_call.args}

            # 这里模拟 Search 工具的返回，实际项目可替换成真实搜索结果
            mocked_tool_result = {
                "query": tool_args_obj.get("query", "英伟达 最新 GPU"),
                "results": [
                    {
                        "title": "NVIDIA GeForce RTX 5090 发布信息",
                        "snippet": "据多家科技媒体报道，RTX 5090 被认为是当前最新一代旗舰消费级 GPU。",
                        "url": "https://example.com/nvidia-rtx-5090",
                    }
                ],
            }
            mocked_tool_result_text = json.dumps(mocked_tool_result, ensure_ascii=False)
            print(f"mocked_tool_result: {mocked_tool_result_text}")

            followup_messages = [
                *exampleMessages,
                {
                    "role": "assistant",
                    "content": response_data.text or "",
                    "tool_calls": [
                        {
                            "id": first_tool_call.call_id,
                            "type": "function",
                            "function": {
                                "name": first_tool_call.name,
                                "arguments": first_tool_call.args,
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "tool_call_id": first_tool_call.call_id,
                    "content": mocked_tool_result_text,
                },
            ]

            print("\n--- 第2轮调用LLM（消费工具结果并产出最终答案） ---")
            final_response = llmClient.think(
                followup_messages,
                stream=True,
            )
            print("\n\n--- 最终模型响应 ---")
            print(final_response.text or "[无文本内容]")
            print(f"finish_reason: {final_response.finish_reason}")
            print(f"tool_calls: {final_response.tool_calls}")
            print(f"usage: {final_response.usage}")

    except ValueError as e:
        print(e)


