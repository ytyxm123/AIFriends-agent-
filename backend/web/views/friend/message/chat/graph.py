import os
from typing import Annotated, TypedDict, Sequence

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.constants import START, END
from langgraph.graph import add_messages, StateGraph


class ChatGraph:
    @staticmethod
    def create_app():
        llm = ChatOpenAI(
            model='deepseek-v3.2',
            openai_api_key=os.getenv('API_KEY'),
            openai_api_base=os.getenv('API_BASE')
        )

        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]
        def model_call(state: AgentState)->AgentState:
            res = llm.invoke(state['messages'])#调用大模型
            return {
                'messages': [res],
            }
        graph = StateGraph(AgentState)

        graph.add_node('model_call')
        graph.add_edge(START, 'agent')
        graph.add_edge('agent', END)

        return graph.compile()

