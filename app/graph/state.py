from typing import Any
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    # --- inputs ---
    report_code: str
    fight_id: int

    # --- populated by fetch_data node ---
    fight_meta: dict[str, Any]      # boss name, duration, outcome
    actors: list[dict[str, Any]]    # player roster
    death_events: list[dict]        # raw death events from FFLogs
    cast_events: list[dict]         # raw cast events
    buff_events: list[dict]         # raw buff apply/remove events
    damage_events: list[dict]       # raw damage events (for overkill)

    # --- populated by parallel analyst nodes ---
    deaths: list[dict[str, Any]]            # structured DeathEvent dicts
    performance_flags: list[dict[str, Any]] # structured PerformanceFlag dicts

    # --- populated by summariser node ---
    summary: str
    context: str            # serialised plain-text context for Q&A
    analysis: dict[str, Any]  # final AnalysisResult dict for the API response
