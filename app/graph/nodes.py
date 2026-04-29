from app.fflogs.client import FFLogsClient
from app.analysis.buffs import ALL_RAID_BUFF_IDS
from app.graph.state import GraphState
from langchain_openai import ChatOpenAI

SYSTEM_PROMPT = (
    "You are a FFXIV raid log analyst. "
    "Describe what happened factually and concisely. "
    "Do NOT give improvement suggestions or coaching advice. "
    "When asked about a death, explain the circumstances (debuffs, overkill, killing hit). "
    "When asked about performance, state what the numbers show."
)

# --------------------------------------------------------------------------- #
# Node 1 — fetch all raw data from FFLogs                                     #
# --------------------------------------------------------------------------- #

async def fetch_data(state: GraphState) -> GraphState:
    code = state["report_code"]
    fight_id = state["fight_id"]

    async with FFLogsClient() as client:
        fights = await client.get_fights(code)
        actors = await client.get_actors(code)

        death_events  = await client.get_events(code, fight_id, "Deaths")
        cast_events   = await client.get_events(code, fight_id, "Casts")
        buff_events   = await client.get_events(code, fight_id, "Buffs")
        damage_events = await client.get_events(code, fight_id, "DamageTaken")

    fight = next((f for f in fights if f["id"] == fight_id), None)
    if fight is None:
        raise ValueError(f"Fight {fight_id} not found in report {code}")

    duration_sec = (fight["endTime"] - fight["startTime"]) / 1000

    return {
        **state,
        "fight_meta": {
            "boss": fight["name"],
            "duration_sec": duration_sec,
            "outcome": "kill" if fight.get("kill") else "wipe",
            "fight_percent": fight.get("fightPercentage"),
        },
        "actors": actors,
        "death_events": death_events,
        "cast_events": cast_events,
        "buff_events": buff_events,
        "damage_events": damage_events,
    }


# --------------------------------------------------------------------------- #
# Node 2a — analyse deaths                                                     #
# --------------------------------------------------------------------------- #

async def death_analyst(state: GraphState) -> GraphState:
    actor_map: dict[int, dict] = {a["id"]: a for a in state.get("actors", [])}
    fight_start = 0  # events use relative timestamps from fight start

    deaths = []
    for event in state.get("death_events", []):
        target_id = event.get("targetID")
        actor = actor_map.get(target_id, {})
        if actor.get("type") != "Player":
            continue

        timestamp_sec = event.get("timestamp", 0) / 1000

        # Collect buffs/debuffs active on the player just before death.
        # TODO M2: build a proper snapshot by replaying applybuff/removebuff events up to timestamp.
        active_buffs: list[str] = []
        active_debuffs: list[str] = []

        # Find the killing hit in damage events (highest overkill near death timestamp).
        killing_ability = "Unknown"
        overkill_dmg = 0
        for dmg in state.get("damage_events", []):
            if (
                dmg.get("targetID") == target_id
                and dmg.get("overkill", 0) > 0
                and abs(dmg.get("timestamp", 0) / 1000 - timestamp_sec) < 2
            ):
                if dmg["overkill"] > overkill_dmg:
                    overkill_dmg = dmg["overkill"]
                    killing_ability = dmg.get("abilityName", "Unknown")

        deaths.append({
            "player": actor.get("name", "Unknown"),
            "job": actor.get("subType", "Unknown"),
            "timestamp_sec": timestamp_sec,
            "overkill_dmg": overkill_dmg,
            "killing_ability": killing_ability,
            "active_debuffs": active_debuffs,
            "active_buffs": active_buffs,
        })

    return {**state, "deaths": deaths}


# --------------------------------------------------------------------------- #
# Node 2b — analyse performance                                                #
# --------------------------------------------------------------------------- #

async def performance_analyst(state: GraphState) -> GraphState:
    actor_map: dict[int, dict] = {a["id"]: a for a in state.get("actors", [])}
    fight_duration = state["fight_meta"]["duration_sec"]
    flags: list[dict] = []

    # --- interrupted casts ---
    interrupt_counts: dict[int, int] = {}
    for event in state.get("cast_events", []):
        if event.get("type") == "begincast":
            # If a begincast has no matching cast event within ~5s, it's interrupted.
            # TODO M3: pair begincast/cast events properly by sourceID + abilityGameID.
            pass
        if event.get("type") == "interrupt":
            src = event.get("sourceID")
            interrupt_counts[src] = interrupt_counts.get(src, 0) + 1

    for actor_id, count in interrupt_counts.items():
        actor = actor_map.get(actor_id, {})
        if actor.get("type") != "Player":
            continue
        flags.append({
            "player": actor.get("name", "Unknown"),
            "job": actor.get("subType", "Unknown"),
            "issue": "interrupted_casts",
            "detail": f"{count} interrupted cast(s)",
        })

    # --- missed raid buff windows ---
    # Collect time windows when each raid buff was active.
    buff_windows: list[tuple[float, float]] = []
    active_buffs: dict[tuple[int, int], float] = {}  # (abilityID, targetID) → start_time

    for event in state.get("buff_events", []):
        ability_id = event.get("abilityGameID")
        if ability_id not in ALL_RAID_BUFF_IDS:
            continue
        key = (ability_id, event.get("targetID", 0))
        if event["type"] == "applybuff":
            active_buffs[key] = event["timestamp"] / 1000
        elif event["type"] == "removebuff" and key in active_buffs:
            buff_windows.append((active_buffs.pop(key), event["timestamp"] / 1000))

    # TODO M3: compare each player's cast timeline against buff windows to detect misses.

    # --- low uptime ---
    # TODO M3: calculate active GCD time per player from cast events vs fight duration.

    return {**state, "performance_flags": flags}


# --------------------------------------------------------------------------- #
# Node 3 — summarise with LLM                                                  #
# --------------------------------------------------------------------------- #

def _build_context(state: GraphState) -> str:
    meta = state["fight_meta"]
    lines = [f"Fight: {meta['boss']} | Duration: {meta['duration_sec']:.0f}s | Outcome: {meta['outcome']}\n"]

    deaths = state.get("deaths", [])
    if deaths:
        lines.append("Deaths:")
        for d in deaths:
            lines.append(
                f"  - {d['player']} ({d['job']}) at {d['timestamp_sec']:.0f}s"
                f" — killed by {d['killing_ability']}, overkill {d['overkill_dmg']}"
                f", debuffs: {d['active_debuffs'] or 'none'}"
                f", buffs: {d['active_buffs'] or 'none'}"
            )
    else:
        lines.append("Deaths: none")

    flags = state.get("performance_flags", [])
    if flags:
        lines.append("\nPerformance flags:")
        for f in flags:
            lines.append(f"  - {f['player']} ({f['job']}): {f['issue']} — {f['detail']}")
    else:
        lines.append("\nPerformance flags: none")

    return "\n".join(lines)


async def summariser(state: GraphState, llm: ChatOpenAI) -> GraphState:
    context = _build_context(state)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Here is the fight data:\n\n{context}\n\nSummarise what happened."},
    ]
    response = await llm.ainvoke(messages)

    analysis = {
        "fight": state["fight_meta"],
        "deaths": state.get("deaths", []),
        "performance_flags": state.get("performance_flags", []),
    }

    return {
        **state,
        "context": context,
        "summary": response.content,
        "analysis": analysis,
    }
