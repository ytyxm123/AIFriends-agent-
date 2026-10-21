# 天气 MCP 工具

文件：`backend/mcp_servers/weather.py`。
提供 `get_weather(city, days=3, country_code="CN")`，查询当前天气与从今天开始的天气预报。
数据来源为 Open-Meteo，当前天气为模式估算；公共接口无需密钥，用于个人非商业演示。
许可：https://open-meteo.com/en/pricing

## 页面配置

在 MCP 工具管理页面添加服务：

- 名称：`weather`
- 连接方式：`本地进程 · stdio`
- 启动命令：`D:\jobs\LLM\AIFriends\.venv\Scripts\python.exe`
- 命令参数：下面的 JSON 数组
- 环境变量：留空
- 连续失败上限：3
- 启用：打开

```json
["D:/jobs/LLM/AIFriends/backend/mcp_servers/weather.py"]
```

保存后依次点击“测试”“同步工具”，确认 `get_weather` 已启用。
stdio 由项目按需启动子进程，无需另外开终端运行天气服务。
换电脑时更换 Python 和脚本的路径；补充依赖用 `pip install -r requirements-mcp.txt`。

## 验证

聊天输入：“请调用 get_weather 查询杭州未来三天的天气。”
Trace 详情应出现 `get_weather` 的参数和返回值，数据中包含 `source=Open-Meteo`。
直接获得回答还不足以证明使用了 MCP，应检查工具调用记录。
如果中文城市名找不到，可尝试 `Hangzhou` 等英文名或拼音。
联网失败或超时时返回工具错误，不生成虚构天气。
