import logging
from app.fflogs.client import FFLogsClient
from app.analysis.buffs import ALL_RAID_BUFF_IDS
from app.graph.state import GraphState
from langchain_openai import ChatOpenAI

log = logging.getLogger(__name__)

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
    log.info("fetch_data: report=%s fight=%s", code, fight_id)

    async with FFLogsClient() as client:
        fights = await client.get_fights(code)
        actors = await client.get_actors(code)
        log.info("fetch_data: found %d fights, %d actors", len(fights), len(actors))

        death_events  = await client.get_events(code, fight_id, "Deaths")
        cast_events   = await client.get_events(code, fight_id, "Casts")
        buff_events   = await client.get_events(code, fight_id, "Buffs")
        damage_events = await client.get_events(code, fight_id, "DamageTaken")
        log.info(
            "fetch_data: events fetched — deaths=%d casts=%d buffs=%d damage=%d",
            len(death_events), len(cast_events), len(buff_events), len(damage_events),
        )

    fight = next((f for f in fights if f["id"] == fight_id), None)
    if fight is None:
        raise ValueError(f"Fight {fight_id} not found in report {code}")

    duration_sec = (fight["endTime"] - fight["startTime"]) / 1000
    outcome = "kill" if fight.get("kill") else "wipe"
    log.info("fetch_data: fight=%r duration=%.0fs outcome=%s", fight["name"], duration_sec, outcome)

    # Return only the keys this node populates.
    return {
        "fight_meta": {
            "boss": fight["name"],
            "duration_sec": duration_sec,
            "outcome": outcome,
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
    log.info("death_analyst: processing %d death events", len(state.get("death_events", [])))
    actor_map: dict[int, dict] = {a["id"]: a for a in state.get("actors", [])}

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

        # Find the killing hit: damage event with highest overkill within 2s of the death.
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
        log.info(
            "death_analyst: %s (%s) died at %.0fs — %s overkill=%d",
            actor.get("name"), actor.get("subType"), timestamp_sec, killing_ability, overkill_dmg,
        )

    log.info("death_analyst: done, %d player deaths", len(deaths))
    # Return only the key this node populates.
    return {"deaths": deaths}


# --------------------------------------------------------------------------- #
# Node 2b — analyse performance                                                #
# --------------------------------------------------------------------------- #

async def performance_analyst(state: GraphState) -> GraphState:
    log.info("performance_analyst: processing events")
    actor_map: dict[int, dict] = {a["id"]: a for a in state.get("actors", [])}
    flags: list[dict] = []

    # --- interrupted casts ---
    interrupt_counts: dict[int, int] = {}
    for event in state.get("cast_events", []):
        if event.get("type") == "interrupt":
            src = event.get("sourceID")
            interrupt_counts[src] = interrupt_counts.get(src, 0) + 1
        # TODO M3: pair begincast/cast events to detect unconfirmed interrupts.

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
        log.info("performance_analyst: %s interrupted %d cast(s)", actor.get("name"), count)

    # --- missed raid buff windows ---
    active_buffs: dict[tuple[int, int], float] = {}  # (abilityID, targetID) → start_time
    buff_windows: list[tuple[float, float]] = []

    for event in state.get("buff_events", []):
        ability_id = event.get("abilityGameID")
        if ability_id not in ALL_RAID_BUFF_IDS:
            continue
        key = (ability_id, event.get("targetID", 0))
        if event["type"] == "applybuff":
            active_buffs[key] = event["timestamp"] / 1000
        elif event["type"] == "removebuff" and key in active_buffs:
            buff_windows.append((active_buffs.pop(key), event["timestamp"] / 1000))

    log.info("performance_analyst: %d raid buff windows detected", len(buff_windows))
    # TODO M3: compare player cast timelines against buff windows.
    # TODO M3: calculate GCD uptime per player.

    log.info("performance_analyst: done, %d flags", len(flags))
    # Return only the key this node populates.
    return {"performance_flags": flags}


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
    log.info("summariser: building context and calling LLM")
    context = _build_context(state)
    log.debug("summariser: context =\n%s", context)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Here is the fight data:\n\n{context}\n\nSummarise what happened."},
    ]
    response = await llm.ainvoke(messages)
    log.info("summariser: LLM responded (%d chars)", len(response.content))

    analysis = {
        "fight": state["fight_meta"],
        "deaths": state.get("deaths", []),
        "performance_flags": state.get("performance_flags", []),
    }

    # Return only the keys this node populates.
    return {
        "context": context,
        "summary": response.content,
        "analysis": analysis,
    }
