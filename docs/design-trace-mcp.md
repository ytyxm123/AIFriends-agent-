# 扩展设计：全链路可观测 Trace + MCP 动态工具接入

本文档描述 Trace 调用记录和 MCP 动态工具接入的设计，用于查看调用耗时、异常及工具执行过程。用户点赞、点踩功能已移除。

---

## 一、全链路可观测 Trace

### 1. 解决的实际问题

LLM 应用上线后是黑盒：回答为什么变差、用户为什么不满意、钱花在哪里、哪一步慢，全部查不到。Trace 模块记录每次对话的完整链路，相当于自研一个轻量 LangSmith。

### 2. 数据模型

**Trace（一次对话请求）**

| 字段 | 类型 | 说明 |
|---|---|---|
| trace_id | UUID | 对外唯一标识 |
| user | FK UserProfile | 索引 |
| friend | FK Friend | 索引 |
| input | Text | 用户输入 |
| output | Text | 最终回复，可能为空 |
| status | choices | running / success / failed |
| model | CharField | 聊天模型名 |
| started_at / ended_at | DateTime | |
| duration_ms | Integer | 总耗时 |
| input_tokens / output_tokens / total_tokens | Integer | |
| cost | Float | 费用（元），按模型单价计算 |
| error | CharField | 错误类型/摘要 |

**Span（一次调用步骤，构成时间线）**

| 字段 | 类型 | 说明 |
|---|---|---|
| trace | FK Trace | |
| span_type | choices | llm / tool / retrieval / tts / asr |
| name | CharField | 如 model_call、search_knowledge_base、cosyvoice-tts |
| status | choices | running / success / failed |
| started_at / ended_at / duration_ms | | |
| input | JSON | 工具参数、prompt 等 |
| output | Text | 工具结果、模型输出（截断保护） |
| model | CharField | llm 类型使用 |
| input_tokens / output_tokens | Integer | llm 类型使用 |
| error | Text | |
| order | Integer | 时间线排序 |

### 3. 埋点方式（最小侵入）

- 新增 `observability/recorder.py`：`TraceRecorder` 负责创建 Trace、记录 Span、结束收尾。
- 新增 `observability/callbacks.py`：`TraceCallbackHandler(BaseCallbackHandler)`，通过 LangChain/LangGraph 的 `config={"callbacks":[handler]}` 自动捕获：
  - `on_chat_model_start/end` → llm span（含模型、token、耗时）
  - `on_tool_start/end` → tool span（含工具名、参数、结果）
  - Agent 循环中的多次 LLM 调用自然形成多条 span。
- Span 在内存中收集，流式结束时批量落库（避免异步回调里频繁写 DB）。
- Trace 在请求进入 `post` 时立即创建（running），无论流是否成功，失败也能在后台看到。
- TTS 不在 LangGraph 内，由 recorder 手动记录 span（连接建立、finish 时间）。

### 4. 成本计算

- `observability/pricing.py`：维护模型单价表（每百万 token 输入/输出价格，元），支持 settings/env 覆盖。
- 模型名按前缀匹配；找不到价格时 cost=0。
- `cost = input_tokens * price_in + output_tokens * price_out`。

### 5. 请求标识

- SSE 首条事件携带 `{"trace_id": "..."}`，供请求排查使用，不提供用户评价入口。

### 6. 管理后台（前端页面，staff 权限）

- **概览页 `/admin/traces/`**：统计卡片（总请求数、成功率、平均响应时长、总 token、总成本），支持时间范围（今日/近 7 天/近 30 天）。
- **Trace 列表**：时间、用户、好友、模型、状态、耗时、token、成本；接口支持按状态/模型筛选及用户名搜索、分页。
- **Trace 详情 `/admin/traces/:trace_id/`**：输入/输出、Span 瀑布时间线（按开始时间与时长绘制，颜色区分类型），每个 span 可展开查看输入输出。

### 7. 后端 API

```
GET  /api/observability/stats/?days=7
GET  /api/observability/traces/?days=&status=&model=&keyword=&items_count=
GET  /api/observability/traces/<trace_id>/
```

---

## 二、MCP 动态工具接入

### 1. 解决的实际问题

现有工具（时间、知识库检索）写死在代码里，新增一个工具要改代码、重启服务。MCP（Model Context Protocol）是 Agent 工具接入的工业标准，支持运行时动态挂载外部工具。

### 2. 数据模型

**MCPServer**

| 字段 | 类型 | 说明 |
|---|---|---|
| name | CharField unique | 标识 |
| transport | choices | stdio / sse / streamable_http |
| command | CharField blank | stdio：可执行文件，如 npx/uvx |
| args | JSON list | stdio 参数 |
| env | JSON dict | stdio 环境变量（含 token，不回显） |
| url | URLField blank | sse / http 的地址 |
| enabled | Boolean | |
| status | choices | unknown / healthy / unhealthy |
| failure_count | Integer | 连续失败次数，用于熔断 |
| last_connected_at | DateTime | |
| last_error | CharField | |

**MCPTool**

| 字段 | 类型 | 说明 |
|---|---|---|
| server | FK MCPServer | |
| name | CharField | unique(server, name) |
| description | TextField | |
| input_schema | JSON | 工具入参 schema |
| enabled | Boolean | |
| last_seen_at | DateTime | |

### 3. 运行时连接策略（工程权衡）

- 现状是每次请求在独立线程 `asyncio.run` 中构建 graph 并流式执行；MCP 连接绑定 event loop，无法跨请求复用。
- **第一版采用「请求级连接」**：在请求线程的事件循环内创建 `MultiServerMCPClient`，并发连接所有启用且未熔断的 server，拉取工具后合并进 graph，请求结束关闭连接。
  - 优点：无跨 loop 问题，简单可靠。
  - 连接总预算（默认 15s）与单 server 超时（默认 8s），并发连接，单个失败不影响其他。
- **熔断**：`failure_count >= 3` 的 server 直接跳过；运行时失败累计计数，健康检查探活成功后清零。
- 后续演进方向：常驻 registry 线程 + 专用 loop 的连接池（README 中如实标注，当前遵循先正确后优化）。

### 4. 图构建改造

- `graph.py` 的 `create_app()` 改为 `async create_app_async()`：
  1. 静态工具（时间、知识库检索）保持不变；
  2. 读取启用且未熔断的 MCPServer；
  3. `MultiServerMCPClient` 并发连接、拉取工具（`return_exceptions` 隔离失败）；
  4. 合并静态工具与 MCP 工具，`bind_tools`；
  5. 返回 `(app, client)`，请求结束后 `finally` 关闭。
- `chat.py` 在 work 协程内构建 graph，inputs 组装逻辑不变。

### 5. 管理 API（staff 权限）

```
GET    /api/mcp/servers/
POST   /api/mcp/servers/
PATCH  /api/mcp/servers/<id>/
DELETE /api/mcp/servers/<id>/
POST   /api/mcp/servers/<id>/test_connection/   # 测试连接，返回拉取到的工具
POST   /api/mcp/servers/<id>/refresh_tools/     # 连接并同步工具到 MCPTool
POST   /api/mcp/servers/<id>/toggle/
GET    /api/mcp/tools/
POST   /api/mcp/tools/<id>/toggle/
```

- 新增 management 命令 `mcp_healthcheck`（可周期执行），探活所有 server 并更新状态/熔断。

### 6. 管理前端（staff 权限）

- `/admin/mcp/`：
  - Server 列表：名称、传输方式、状态、失败次数、工具数、启用开关；
  - 添加/编辑表单：根据传输方式展示 stdio（command/args/env）或 URL 参数；
  - 「测试连接」「刷新工具」按钮，即时反馈结果；
  - 工具列表：名称、描述、schema 查看、启停。

### 7. 安全

- 所有 MCP 管理接口与页面要求 `is_staff`。
- stdio `command` 走白名单（默认 `npx`、`uvx`、`python`，可配置），防止任意命令执行。
- env 字段写入后不回显；工具调用设置超时（默认 30s）；连接错误只返回通用提示，不泄露内部地址。

---

## 三、实施顺序

1. **Trace 后端**（模型、埋点、反馈、成本、测试）
2. **Trace 前端**（反馈按钮、概览、列表、详情）
3. **MCP 后端**（模型、async 改造、管理 API、健康检查、测试）
4. **MCP 前端**（管理页面、接入真实 MCP server 联调）
5. **收尾**（Django admin 注册、README/文档、部署、简历描述）

每个阶段完成后运行 `manage.py test` 与 `npm run build` 验证。

## 四、新增依赖

- 后端：`mcp`、`langchain-mcp-adapters`（需验证 Python 3.14 兼容性）
- 无新增前端依赖
