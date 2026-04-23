# FanFrame Roadmap

## 0. 目标与原则

- 目标：构建一个可扩展、可观测、可测试的 Agent 框架，优先保证稳定闭环，再扩展高级能力。
- 研发原则：
  - 核心链路优先：`输入 -> 推理 -> 工具 -> 反馈 -> 输出`
  - 协议先行：消息、tool call、memory query 全部结构化
  - 可观测优先：没有 trace 的能力不可长期维护
  - 渐进增强：先单 Agent 跑稳，再多 Agent/skill 化

优先级定义：
- `P0`：必须先做；不做会阻塞主流程
- `P1`：强烈建议；影响效果和可维护性
- `P2`：增强项；不阻塞主流程

---

## 1. 核心模块（Core Runtime）

### 1.1 LLM Gateway（模型网关）
- `P0`
  - 自动读取配置（model/api_key/base_url/timeout）
  - 本地模型调用（兼容 OpenAI API 风格）
  - 流式/非流式统一返回结构（text/tool_calls/finish_reason/usage）
- `P1`
  - provider fallback（主模型失败自动切备）
  - 统一异常分类（网络超时、限流、鉴权）
- `P2`
  - 响应缓存（可选）
  - 请求级成本统计与预算控制

### 1.2 Tool System（工具系统）
- `P0`
  - 工具注册与调用
  - 工具 schema（参数校验）
  - 统一 tool call 协议（`name + args + call_id`）
- `P1`
  - 固定目录自动加载（插件扫描 + 白名单）
  - 工具错误重试策略（可重试/不可重试）
- `P2`
  - 工具权限分级（read-only/network/shell）
  - 工具调用并发与限流

### 1.3 Orchestrator（运行时编排）
- `P0`
  - 标准 loop：`think -> decide -> tool -> observe -> answer`
  - 终止条件：max_steps / timeout / fail_count
  - 统一输出：final_answer + steps + tool_traces
- `P1`
  - 状态机化（idle/running/waiting_tool/finished/error）
  - 中断恢复（checkpoint）
- `P2`
  - 多轮会话恢复执行
  - 任务优先级调度

### 1.4 Agent 基础能力
- `P0`
  - ReAct Agent（最小可用）
- `P1`
  - Planner Agent（任务拆解）
  - Reviewer Agent（自检与纠错）
- `P2`
  - Router Agent（多 Agent 分发）
  - 多 Agent 协作模式（串行/并行）

---

## 2. 关键增强模块（Memory & Skills）

### 2.1 Memory（记忆系统）
- `P0`
  - 短期记忆（会话历史窗口）
  - 长期记忆存储接口（先抽象，后具体实现）
  - top-k 检索注入（禁止全量注入）
- `P1`
  - 压缩（summarize）与提取（facts/preferences）
  - 长短期管理策略（promote/forget）
- `P2`
  - 冲突事实解决与版本演进
  - 用户画像分层记忆

### 2.2 Skill System（技能系统）
- `P0`
  - skill 抽象（name/description/trigger/steps/version）
  - skill 执行器（可调用 tool、可产出中间状态）
- `P1`
  - 触发策略（规则 + LLM 判断）
  - 版本管理（兼容旧 skill）
- `P2`
  - skill 市场化加载（外部包）
  - skill 评测与排名

---

## 3. 支撑模块（Config / Observability / QA）

### 3.1 Config（配置系统）
- `P0`
  - 自动加载配置（env + file）
  - 运行时热切换（temperature/model/max_tokens）
- `P1`
  - 分环境配置（dev/test/prod）
  - 配置校验与启动自检
- `P2`
  - 远程配置中心（可选）

### 3.2 可调试性（Observability）
- `P0`
  - 结构化日志（session_id/turn_id/call_id）
  - trace 链路（LLM/tool/memory 全链路）
- `P1`
  - 回放系统（按 session 重放）
  - 调试模式（verbose + 中间状态输出）
- `P2`
  - 调试面板 UI（可视化步骤/耗时/错误）
  - 运行指标看板（吞吐、延迟、成功率）

### 3.3 评价与测试（Evaluation & Testing）
- `P0`
  - 单元测试：message/config/tool_executor/orchestrator
  - 集成测试：mock LLM + mock tool，完整 loop
- `P1`
  - 回归任务集（固定 benchmark）
  - 关键路径稳定性测试（超时/重试/失败恢复）
- `P2`
  - 自动评测流水线（CI nightly）
  - 多模型对比评测

---

## 4. 边缘模块（DX & Productization）

### 4.1 CLI 命令化
- `P0`
  - `chat` / `run` / `tools` 三个子命令
- `P1`
  - `replay` / `eval` / `config` 子命令
- `P2`
  - profile、session 管理、批处理执行

### 4.2 Demo
- `P0`
  - 最小闭环 demo（问答 + 一个工具）
- `P1`
  - memory demo、multi-agent demo
- `P2`
  - 端到端场景 demo（真实任务脚本）

### 4.3 文档
- `P0`
  - 快速开始、架构总览、扩展指南（tool/agent）
- `P1`
  - 运维与调试手册
- `P2`
  - 最佳实践与案例库

---

## 5. 开发计划（按里程碑）

## M1：打通核心闭环（1~2 周）
目标：单 Agent 稳定可用
- 完成：
  - LLM Gateway `P0`
  - Tool System `P0`
  - Orchestrator `P0`
  - ReAct Agent `P0`
  - Config `P0`
  - Observability `P0`
  - 测试：UT + 最小集成测试 `P0`
- 验收：
  - 能稳定执行 `user -> llm -> tool -> llm -> answer`
  - 出错可定位（有 trace）

## M2：提升效果与可维护性（2~3 周）
目标：记忆+规划能力可用，框架可调优
- 完成：
  - Memory `P0 + P1`
  - Planner/Reviewer `P1`
  - Tool 自动加载 `P1`
  - 回放 `P1`
  - 回归集 `P1`
- 验收：
  - 长对话不明显退化
  - 能回放并复现关键失败 case

## M3：能力扩展与产品化（2~4 周）
目标：可扩展、可演示、可持续演进
- 完成：
  - Router Agent `P2（可提前到P1）`
  - Skill System `P0 + P1`
  - CLI 扩展 `P1`
  - Demo + 文档 `P0/P1`
  - 调试面板 `P2`
- 验收：
  - 具备多 Agent/skill 扩展能力
  - 新人可按文档在 30 分钟内跑通 demo

---

## 6. 风险与缓解

- 风险：过早做多 Agent 导致复杂度飙升  
  - 缓解：M1 只做单 Agent + Orchestrator
- 风险：memory 注入过量导致上下文污染  
  - 缓解：强制 top-k + 摘要注入
- 风险：工具协议不统一导致维护困难  
  - 缓解：先定 schema 与统一 tool call 协议
- 风险：没有评测导致“改好了但变差了”  
  - 缓解：M2 前建立最小回归集

---

## 7. Definition of Done（DoD）

每个模块完成必须满足：
- 代码：接口稳定、最小注释、示例可运行
- 测试：核心路径至少 1 条集成测试通过
- 可观测：关键步骤可追踪、错误可定位
- 文档：新增能力有最小使用说明