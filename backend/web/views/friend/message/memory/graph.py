import os
from typing import TypedDict, Annotated, Sequence

from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
from langgraph.constants import START, END
from langgraph.graph import add_messages, StateGraph
from web.views.friend.message.memory.config import setting


class MemoryGraph:
    @staticmethod
    def create_app():
        llm = ChatOpenAI(
            model=setting('MODEL'),
            openai_api_key=os.getenv('MEMORY_API_KEY') or os.getenv('API_KEY'),
            openai_api_base=os.getenv('MEMORY_API_BASE') or os.getenv('API_BASE'),
            temperature=0,
            timeout=setting('MODEL_TIMEOUT'),
            max_retries=0,
            max_tokens=2000,
            model_kwargs={'response_format': {'type': 'json_object'}},
        )

        class AgentState(TypedDict):
            messages: Annotated[Sequence[BaseMessage], add_messages]

        def model_call(state: AgentState)->AgentState:
            res = llm.invoke(state['messages'])
            return{'messages': [res]}
        graph = StateGraph(AgentState)

        graph.add_node('agent', model_call)


        graph.add_edge(START, 'agent')

        graph.add_edge('agent', END)

        return graph.compile()
