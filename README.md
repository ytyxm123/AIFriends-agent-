# AIFriends 智能交互平台

基于 Django、Vue 3 和 LangGraph 的单 Agent 交互平台。在角色化连续对话中，让模型按需检索知识、调用内置或 MCP 工具，并通过近期消息、历史摘要和结构化事实保持对话连续性。

本项目用于学习和项目演示，不是多智能体系统。大模型、Embedding、语音识别与合成通过外部 API 调用，无需在本地部署大模型；API 使用可能产生费用。

## 实现内容

| 模块 | 实现与目的 |
| --- | --- |
| Agent 工作流 | 模型推理与工具执行分离，通过 tool_calls 路由并回填结果；限制工具执行轮数，识别连续重复调用，避免无效循环 |
| RAG 知识检索 | 文本切分并向量化，使用 LanceDB 检索相关片段；检索封装为 Tool，由模型按需调用 |
| 分层对话记忆 | 最近消息窗口、滚动摘要和结构化事实组合进入上下文；记忆按用户与角色隔离，保留来源及修订历史 |
| 记忆增量更新 | 每累计 10 轮未处理对话，在回复保存后整理摘要及事实；页面提示“正在优化对话”，不需要独立 Worker |
| MCP 工具接入 | 配置外部服务、测试连接、同步和启停工具；连接超时与服务异常隔离，保留内置工具和基础聊天 |
| Trace 调用追踪 | 记录模型、检索、工具与语音步骤，查看耗时、输入输出、Token 和错误；费用为估算，不等于服务商账单 |
| 流式与语音交互 | SSE 返回文字和可选音频；文字生成与语音连接并行，语音失败时继续文字回复 |
| 用户与角色 | 注册登录、JWT 刷新、角色创建、独立聊天历史；管理页面仅供管理员使用 |

### 请求链路

```text
用户消息 → JWT 鉴权 → 角色设定 + 近期消息 + 相关长期记忆
                    ↓
               LangGraph Agent
          ┌─────────┴─────────────┐
          直接回答       时间 / RAG / MCP 工具
                            ↓
                       结果回填模型
          └─────────┬─────────────┘
                 SSE 回复
                    ↓
                保存聊天记录
                    ↓
       满 10 轮后整理摘要和事实 → 结束请求
```

记忆抽取需要引用本批用户原话，同一属性通过稳定 key 更新；摘要、事实与处理游标在一个事务内提交。调用失败不推进游标，在后续成功聊天后重试。来源校验不等于语义正确性保证；上下文预算、候选数和召回规则见[记忆说明](docs/agent-memory.md)。

## 技术栈

- 后端：Django、Django REST Framework、SimpleJWT。
- Agent：LangGraph、LangChain、OpenAI 兼容模型 API。
- 存储：SQLite 保存业务数据与记忆；LanceDB 保存知识库向量。
- 前端：Vue 3、Pinia、Vue Router、Tailwind CSS、DaisyUI。
- 工具与交互：MCP、SSE、WebSocket、MediaSource。
- 默认模型：DeepSeek 用于聊天，qwen-plus 整理记忆，text-embedding-v4 向量化，cosyvoice-v3-flash 用于可选语音。模型可用性、地域和额度以服务商控制台为准。

## 本地运行

以下命令以 Windows PowerShell 为例，每个终端从项目根目录开始。本次开发验证使用 Python 3.14；前端需要 Node.js 22.18+（22 系列）或 24.12+。其他 Python 版本及 Linux 部署需另行验证依赖兼容性。

### 1 安装与配置

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

如果本地已有环境文件，不要覆盖。根 requirements.txt 已包含 requirements-mcp.txt，MCP 依赖会一并安装。

编辑 backend/.env，填写自己的 API_KEY 与随机 DJANGO_SECRET_KEY，并核对：

- API_BASE / CHAT_MODEL：与你有权限调用的聊天模型匹配。默认聊天模型为 deepseek-v4-flash-0731，不保证每个账号都有权限。
- MEMORY_MODEL / MEMORY_EMBEDDING_MODEL：记忆与向量服务配置，支持单独设置密钥与地址，详见记忆文档。
- ENABLE_TTS=false：首次启动建议只测试文字；语音需要单独配置接口与可用音色。
- 本地前端、后端统一使用 127.0.0.1，分别为 5173 和 8000 端口，避免混用 localhost 导致 Cookie 或跨域问题。

模型密钥只能放后端环境文件。frontend/.env 只配置访问地址，不得存放密钥。

### 2 初始化数据库与知识库

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate
Copy-Item web\documents\data.example.txt web\documents\data.txt
..\.venv\Scripts\python.exe manage.py rebuild_knowledge_base
```

知识库构建会调用 Embedding API。可先跳过构建测试普通聊天，RAG 功能需构建后再验证。已有 data.txt 请自行备份，不要直接覆盖；重建命令会替换同名知识库表。

### 3 启动后端

在新的项目根目录终端执行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

### 4 启动前端

在另一个项目根目录终端执行：

```powershell
Set-Location frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

访问 http://127.0.0.1:5173/ 。runserver 和 Vite dev 仅用于本地开发，不是生产启动方式。

## 首次使用

1. 打开注册页面，创建自己的账号并登录。仓库不包含真实账号或聊天数据库。
2. 进入“创作”，创建角色，填写名称与设定、上传头像和聊天背景。音色可选择“仅文字”。
3. 从首页进入角色聊天，测试连续对话；询问当前时间可验证内置工具。
4. 根据示例知识库的内容提问，并查看 Trace 确认是否实际调用检索工具，而不是仅凭回答文字判断 RAG 生效。
5. 累计达到记忆阈值后，回答保存后会出现“正在优化对话”。不足阈值不显示；原有信息仍可通过近期消息参与回复。

全新数据库没有预置角色、复刻音色及上传图片，首页为空是正常现象。默认头像引用的 media 文件不随仓库分发，可在个人资料上传自己的头像。

## 管理页面

MCP 和 Trace 页面要求 Django 用户的 is_staff=True。首次可创建管理员并初始化其应用资料：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py createsuperuser --username demo_admin
..\.venv\Scripts\python.exe manage.py shell -c "from django.contrib.auth import get_user_model; from web.models.user import UserProfile; UserProfile.objects.get_or_create(user=get_user_model().objects.get(username='demo_admin'))"
```

密码由终端交互输入，不要写入代码。使用该账号登录前端后访问：

- MCP 服务与工具：http://127.0.0.1:5173/admin/mcp/
- Trace 调用记录：http://127.0.0.1:5173/admin/traces/
- Django 数据管理：http://127.0.0.1:8000/admin/

MCP 保留本地工具与动态工具并存，不是所有工具都经过 MCP。支持的连接方式和示例见[天气 MCP 工具](docs/weather-mcp.md)与[Trace / MCP 设计](docs/design-trace-mcp.md)。stdio 服务需要对应的 Python、npx 或 uvx 运行环境，配置中的本机绝对路径须按实际安装位置修改。

MCP 的进程命令和远程地址只能由可信管理员配置；不要把管理员账号提供给公开访客。

## 可选语音

开启 ENABLE_TTS 并配置 WSS_URL、VOICE_URL 和可用音色后启用语音合成。复刻音色与创建时的目标模型绑定，不能直接跨模型复用，迁移和额度说明见[语音模型说明](docs/speech-models.md)。

麦克风输入还需要本地 VAD 资源。在 frontend 目录安装依赖后执行：

```powershell
New-Item -ItemType Directory -Force public/vad
Copy-Item node_modules/@ricky0123/vad-web/dist/*.onnx public/vad/
Copy-Item node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js public/vad/
Copy-Item node_modules/onnxruntime-web/dist/*.wasm public/vad/
Copy-Item node_modules/onnxruntime-web/dist/*.mjs public/vad/
```

VAD 用于浏览器语音活动检测，不是本地大语言模型。生产域名的麦克风访问需要 HTTPS 和浏览器授权；语音识别 API 的额度独立于文字与语音合成服务。

## 测试与构建

在项目根目录运行：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py check
..\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
..\.venv\Scripts\python.exe manage.py test web.test_chat web.test_memory web.test_speech web.test_mcp web.test_observability --noinput

Set-Location ..\frontend
npm run build
```

默认测试不请求付费模型。AGENT_MEMORY_LIVE_TEST=1 和 AIFRIENDS_LIVE_TEST=1 分别启用基于虚构对话的记忆与聊天 API 冒烟测试，会消耗配额；不能据单个冒烟案例宣称生产准确率或容量达标。

## 数据与部署边界

- 不提交真实 .env、聊天数据库及其备份、上传图片、知识库私有文档或本地向量文件。仓库提供示例配置与示例知识文本。
- SQLite 和应用层记忆向量计算面向本地演示，尚未做生产并发压测、容量或安全验收。
- 对外部署需配置正式服务进程、HTTPS、SSE 代理策略、访问限流、备份和 API 消费限制。
- Trace 会记录对话和工具输入输出，管理员应限制访问并制定保留与清理策略。
- 记忆撤销为软标记，不等于彻底删除聊天和版本记录。
- 费用统计只用于排查估算，最终以服务商账单为准。

## 来源与开发范围

项目在原有 AIFriends 代码基础上扩展，保留原 Git 提交历史；原始仓库为 git@git.acwing.com:AYTForever/aifriends.git。当前扩展包括工具循环保护、分层记忆、MCP 接入、Trace 管理及语音故障降级等，不宣称全部基础代码均为从零编写。

本仓库暂未添加开源许可证，公开分发前需确认原项目及相关素材的授权；第三方依赖遵循各自许可证。
