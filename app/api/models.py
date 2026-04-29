from pydantic import BaseModel
from typing import Any

class AnalyzeRequest(BaseModel):
    report_code: str
    fight_id: int

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    context: str
    history: list[ChatMessage] = []
    question: str

class FightSummary(BaseModel):
    id: int
    name: str
    start_time: int
    end_time: int
    kill: bool
    fight_percentage: float | None = None

class DeathEvent(BaseModel):
    player: str
    job: str
    timestamp_sec: float
    overkill_dmg: int
    killing_ability: str
    active_debuffs: list[str]
    active_buffs: list[str]

class PerformanceFlag(BaseModel):
    player: str
    job: str
    issue: str   # "low_uptime" | "interrupted_casts" | "missed_buff_windows"
    detail: str

class AnalysisResult(BaseModel):
    fight: dict[str, Any]
    deaths: list[DeathEvent]
    performance_flags: list[PerformanceFlag]

class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    summary: str
    context: str          # serialised context passed back for Q&A

class ChatResponse(BaseModel):
    answer: str
    history: list[ChatMessage]
