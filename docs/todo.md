### LLM
自动读取配置
本地模型调用

### tool
加载、调用schema
统一tool call
固定地址自动加载

### memory
长短期实现
管理方法
压缩
检索top记忆而非全量注入

### agent
React
planner
reviewer
routeragent

### skill
skill抽象实现
触发
执行
版本

### config
自动加载配置
参数热切换（temperature，model，max_token）

### 可调试性
日志
trace链路
回放
调试面板UI

### 评价与测试
UT
成测试：mock LLM + mock tool，跑完整 agent loop。
回归集：沉淀一批固定任务集，防止改动后能力退化。

### other
cli命令
demo
文档