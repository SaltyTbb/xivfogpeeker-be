from functools import partial
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from app.graph.state import GraphState
from app.graph.nodes import fetch_data, death_analyst, performance_analyst, summariser


def build_graph(llm: ChatOpenAI) -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("fetch_data", fetch_data)
    graph.add_node("death_analyst", death_analyst)
    graph.add_node("performance_analyst", performance_analyst)
    graph.add_node("summariser", partial(summariser, llm=llm))

    graph.set_entry_point("fetch_data")

    # Fan out to both analysts in parallel after data is fetched.
    graph.add_edge("fetch_data", "death_analyst")
    graph.add_edge("fetch_data", "performance_analyst")

    # Both analysts feed into the summariser.
    graph.add_edge("death_analyst", "summariser")
    graph.add_edge("performance_analyst", "summariser")

    graph.add_edge("summariser", END)

    return graph.compile()
