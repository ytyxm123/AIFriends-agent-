import json
import logging
import os

from typing import Annotated, NotRequired, TypedDict, Sequence

from django.utils.timezone import now, localtime
import lancedb

from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.constants import START, END
from langgraph.graph import add_messages, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from web.documents.utils.custom_embeddings import CustomEmbeddings

logger = logging.getLogger(__name__)

DEFAULT_CHAT_MODEL = 'deepseek-v4-flash-0731'


class KnowledgeQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)


def tool_call_signature(message):
    """Build a stable signature used to detect consecutive duplicate tool calls."""
    calls = getattr(message, 'tool_calls', None) or []
    if not calls:
        return ''
    normalized = [
        {'name': call.get('name', ''), 'args': call.get('args', {})}
        for call in calls
    ]
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True)


class ChatGraph:
    @staticmethod
    def static_tools():
        """Built-in tools that do not depend on MCP configuration."""
        @tool
        def get_time()->str:
            """当需要查询时间时，调用此函数。返回格式为：[年-月-日 时:分:秒]"""
            return localtime(now()).strftime("%Y-%m-%d %H:%M:%S")
        @tool(args_schema=KnowledgeQuery)
        def search_knowledge_base(query: str) -> str:
            """当问题需要查询私有知识库时调用。输入检索问题，返回最相关的知识片段。"""
            try:
                db = lancedb.connect('./web/documents/lancedb_storage')
                embeddings = CustomEmbeddings()
                from langchain_community.vectorstores import LanceDB
                vector_db = LanceDB(
                    connection=db,
                    embedding=embeddings,
                    table_name=os.getenv('KNOWLEDGE_TABLE_NAME', 'my_knowledge_base'),
                )
                docs = vector_db.similarity_search(query, k=3)
            except Exception as exc:
                logger.warning('knowledge_search_failed error=%s', type(exc).__name__)
                return '知识库暂时不可用，请基于已有上下文回答，并明确说明未检索到外部资料。'

            content = '\n\n'.join(
                f'内容片段{i + 1}\n{doc.page_content}' for i, doc in enumerate(docs)
            )
            return f'从知识库中找到以下相关信息\n\n{content}'

        return [get_time, search_knowledge_base]

    @staticmethod
    def create_app(extra_tools=None):
        tools = ChatGraph.static_tools() + list(extra_tools or [])
        llm = ChatOpenAI(
            model=os.getenv('CHAT_MODEL', DEFAULT_CHAT_MODEL),
            openai_api_key=os.getenv('API_KEY'),
            openai_api_base=os.getenv('API_BASE'),
            streaming=True,  # 流式输出
            timeout=45,
            max_retries=1,
            model_kwargs={
                "stream_options": {
                    "include_usage": True,  # 输出token消耗数量
                }
            }
        ).bind_tools(tools)

        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]
            tool_rounds: NotRequired[int]
            last_tool_signature: NotRequired[str]
            repeated_tool_calls: NotRequired[int]
        def model_call(state: AgentState)->AgentState:
            res = llm.invoke(state['messages'])#调用大模型
            return {
                'messages': [res],
            }

        async def amodel_call(state: AgentState)->AgentState:
            res = await llm.ainvoke(state['messages'])#异步调用大模型
            return {
                'messages': [res],
            }

        def track_tool_calls(state: AgentState) -> AgentState:
            last_message = state['messages'][-1]
            signature = tool_call_signature(last_message)
            if not signature:
                return {}
            repeated = (
                state.get('repeated_tool_calls', 0) + 1
                if signature == state.get('last_tool_signature', '') else 1
            )
            return {
                'tool_rounds': state.get('tool_rounds', 0) + 1,
                'last_tool_signature': signature,
                'repeated_tool_calls': repeated,
            }

        def should_continue(state: AgentState) -> str:
            if not getattr(state['messages'][-1], 'tool_calls', None):
                return 'end'
            if state.get('tool_rounds', 0) > max(1, int(os.getenv('AGENT_MAX_TOOL_ROUNDS', '4'))):
                return 'limit'
            if state.get('repeated_tool_calls', 0) >= int(os.getenv('AGENT_MAX_REPEAT_CALLS', '2')):
                return 'limit'
            return 'tools'

        def limit_response(state: AgentState) -> AgentState:
            return {
                'messages': [AIMessage(content='工具调用未能收敛，请换一种方式描述问题。')]
            }

        tool_node = ToolNode(tools)

        graph = StateGraph(AgentState)

        graph.add_node('agent', RunnableLambda(model_call, amodel_call))
        graph.add_node('track_tool_calls', track_tool_calls)
        graph.add_node('tools',tool_node)
        graph.add_node('limit_response', limit_response)
        graph.add_edge(START, 'agent')
        graph.add_edge('agent', 'track_tool_calls')
        graph.add_conditional_edges(
            'track_tool_calls',
            should_continue,
            {
                "tools": 'tools',
                "limit": 'limit_response',
                "end":END
            }
        )
        graph.add_edge('tools', 'agent')
        graph.add_edge('limit_response', END)

        return graph.compile()

    @staticmethod
    async def create_app_async():
        """Build the graph with built-in tools plus enabled MCP tools.

        MCP discovery is best-effort: any failure in the dynamic layer falls
        back to the static tools so chat never breaks because of MCP.
        """
        try:
            from web.mcp.client import load_runtime_tools
            mcp_tools = await load_runtime_tools()
        except Exception as exc:
            logger.warning('mcp_runtime_load_failed error=%s: %s',
                           type(exc).__name__, exc)
            mcp_tools = []
        if mcp_tools:
            logger.info('mcp_tools_loaded count=%s names=%s',
                        len(mcp_tools), [t.name for t in mcp_tools])
        return ChatGraph.create_app(extra_tools=mcp_tools)

