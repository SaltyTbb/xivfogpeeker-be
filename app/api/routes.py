from fastapi import APIRouter, HTTPException
from app.api.models import (
    AnalyzeRequest, AnalyzeResponse,
    ChatRequest, ChatResponse, ChatMessage,
    FightSummary,
)
from app.fflogs.client import FFLogsClient
from app.graph.graph import build_graph
from app.graph.state import GraphState
from langchain_openai import ChatOpenAI
import os

router = APIRouter()


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
    )


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/report/{code}", response_model=list[FightSummary])
async def get_fights(code: str):
    async with FFLogsClient() as client:
        fights = await client.get_fights(code)
    return fights


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    llm = get_llm()
    graph = build_graph(llm)

    initial_state = GraphState(
        report_code=req.report_code,
        fight_id=req.fight_id,
    )

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return AnalyzeResponse(
        analysis=final_state["analysis"],
        summary=final_state["summary"],
        context=final_state["context"],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    llm = get_llm()

    system = (
        "You are a FFXIV raid log analyst. "
        "Describe what happened factually and concisely. "
        "Do NOT give improvement suggestions. "
        "When asked about a death, explain the circumstances. "
        "When asked about performance, state what the numbers show."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Fight context:\n\n{req.context}"},
        {"role": "assistant", "content": "Understood. Ask me anything about this fight."},
        *[{"role": m.role, "content": m.content} for m in req.history],
        {"role": "user", "content": req.question},
    ]

    response = await llm.ainvoke(messages)
    answer = response.content

    updated_history = req.history + [
        ChatMessage(role="user", content=req.question),
        ChatMessage(role="assistant", content=answer),
    ]

    return ChatResponse(answer=answer, history=updated_history)
