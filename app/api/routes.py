import logging
import os
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

log = logging.getLogger(__name__)
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
    log.info("GET /report/%s", code)
    async with FFLogsClient() as client:
        fights = await client.get_fights(code)
    log.info("GET /report/%s → %d fights", code, len(fights))
    return fights


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    log.info("POST /analyze report=%s fight=%s", req.report_code, req.fight_id)
    llm = get_llm()
    graph = build_graph(llm)

    initial_state = GraphState(
        report_code=req.report_code,
        fight_id=req.fight_id,
    )

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as e:
        log.exception("graph failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    log.info("POST /analyze done — %d deaths, %d flags", len(final_state["analysis"]["deaths"]), len(final_state["analysis"]["performance_flags"]))
    return AnalyzeResponse(
        analysis=final_state["analysis"],
        summary=final_state["summary"],
        context=final_state["context"],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    log.info("POST /chat question=%r history_len=%d", req.question[:60], len(req.history))
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
