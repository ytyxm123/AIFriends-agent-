# 对话记忆：近期消息 + 历史摘要 + 结构化事实

## 三层内容

- 近期消息：最近 10 轮用户/助手对话，总预算约 4000 token，保留配对和当前问题。
- 历史摘要：保存在 Friend.memory，最多约 600 token，概括此前重要对话。
- 结构化事实：保存在 MemoryFact，记录身份、偏好、事件、关系，包含稳定 key、来源消息、用户原话、版本和可选过期时间。

每个用户与角色对应的 Friend 都有独立记忆。召回时过滤失效、撤销和其他会话的事实，结合关键词/向量相关性、重要性、时间衰减选取最多 6 条；事实和摘要合计约 1600 token。这是限定候选的应用层计算，不是大规模 ANN 索引。

## 何时更新

1. 模型流式回复，语音连接并行建立，不阻塞文字生成。
2. 回复成功后先保存聊天记录。
3. 若累计未整理的对话达到 10 轮，页面提示“正在优化对话…”。
4. 当前聊天请求直接调用记忆模型，一次生成滚动摘要和事实增删改，不需要额外进程。
5. 校验事实是否引用本批次用户原话，一次事务提交事实、版本、摘要、处理游标。
6. 整理完成后结束请求，恢复发送按钮。未到阈值不调用记忆模型，也不显示整理提示。

每次至多处理最早 10 轮积压，不一次回放全部历史。小于 10 轮的尾部仍可通过近期消息进入上下文，累计达到阈值后再整理。

## 失败与并发

- 网络调用在数据库事务之外，不长时间持有数据库锁。
- 模型超时、非法 JSON、来源校验失败时，旧摘要和事实不变、游标不前进，回答保留。下一次成功聊天后再次处理未完成批次，不在当前请求反复重试。
- 提交前比较读取时的游标。并发请求即使计算同一批，也只有一份结果可以提交，旧结果不会覆盖新记忆；不保证消除重复 API 调用费用。
- 同一属性复用稳定 key，纠正信息时更新旧值、保留版本。撤销采用 inactive 软标记，不等于物理删除聊天和审计记录。
- 引用原话校验不能证明模型语义理解一定正确。

## 性能与配置

整理时每轮用户消息最多取 500 token、助手回复最多取 250 token；模型输出最多 2000 token。记忆模型网络超时默认 15 秒，无自动重试。向量请求每批最多 10 条、超时 5 秒；向量故障仍保存事实，读取时退回关键词召回。这些是单次网络超时参数，不是整个整理过程的严格总时限。

默认使用 qwen-plus 整理记忆、text-embedding-v4 生成 1024 维向量，复用现有 API_KEY / API_BASE，不需本地模型。支持 MEMORY_MODEL、MEMORY_USE_EMBEDDINGS、MEMORY_EMBEDDING_MODEL、MEMORY_EMBEDDING_DIMENSIONS 环境变量；独立服务可使用 MEMORY_API_KEY / MEMORY_API_BASE 和 MEMORY_EMBEDDING_API_KEY / MEMORY_EMBEDDING_API_BASE。预算阈值见 memory/config.py，可在 settings.AGENT_MEMORY 覆盖。

## 启动与验证

仅启动 Django 和 Vue。升级后先迁移：

```powershell
Set-Location backend
..\.venv\Scripts\python.exe manage.py migrate
..\.venv\Scripts\python.exe manage.py test web.test_memory web.test_chat --noinput
..\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

迁移保留原有聊天、摘要、事实、版本和处理游标，仅删除旧任务状态、租约和尝试次数字段。旧后台整理命令已删除，不需要第三个终端。

自动化测试默认不请求真实模型，覆盖阈值、提示顺序、超时后重试、冲突修正、隔离、来源校验、事务回滚、过期结果拒绝及语音不阻塞文字。真实模型抽取准确率、P95 延迟和生产并发容量仍需独立评测。设置 AGENT_MEMORY_LIVE_TEST=1 可运行合成数据的付费 API 冒烟测试。

更换向量模型/维度后可用 manage.py memory_reindex --friend-id <ID> 重建历史向量，会调用 embedding API。SQLite 用于本地演示，生产多实例需选择合适数据库并验证并发。
