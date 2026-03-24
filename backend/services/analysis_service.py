"""Analysis service — bridges the API to the Agno team orchestrator."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from agno.team import Team
from tools.market_tool import _resolve_ticker, pre_approve_ticker
from agents.research_agent import create_research_agent, create_session_knowledge
from agents.team_orchestrator import create_financial_sentinel
from schemas.chat_schema import ChatResponse
from services import ingestion_service, upload_service

logger = logging.getLogger(__name__)

_USER_ID = "api_user"

_HIDDEN_EVENT_TYPES = {
    "ToolCallStarted", "ToolCallCompleted", "ToolExecution",
    "ToolExecutionStarted", "ToolExecutionCompleted",
    "AgentRunCompleted", "AgentRunResponse",
    "MemberAgentResponseStarted", "MemberAgentResponseCompleted",
    "TeamMemberResponse",
}

# These event types carry the FULL assembled text (snapshot), not a delta.
# Forwarding them would duplicate everything already sent via delta chunks.
_SNAPSHOT_EVENT_TYPES = {
    "RunResponseContent",
    "RunResponse",
    "AgentRunResponseContent",
    "MemberAgentResponseContent",
    "TeamRunResponseContent",
}

_paused_runs: dict[str, dict] = {}


def _extract_pause_info(pause_event) -> tuple[str | None, list, str, str]:
    agent_run_id: str | None = getattr(pause_event, "run_id", None)
    if not agent_run_id:
        agent_run_id = (
            getattr(pause_event, "session_run_id", None) or
            getattr(pause_event, "id", None)
        )
    requirements: list = (
        getattr(pause_event, "active_requirements", None) or
        getattr(pause_event, "requirements", None) or []
    )
    raw_input = ""
    resolved_ticker = ""
    for req in requirements:
        if getattr(req, "needs_confirmation", False):
            te = getattr(req, "tool_execution", None)
            args = getattr(te, "tool_args", {}) if te else {}
            raw_input = args.get("user_input", "")
            resolved_ticker = _resolve_ticker(raw_input)
            break
    return agent_run_id, requirements, raw_input, resolved_ticker


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_enriched_message(
    message: str,
    attachments: list[str] | None,
    ingestion_warnings: list[str],
    session_id: str,
) -> str:
    parts = []
    if attachments:
        indexed = [fid for fid in attachments if upload_service.is_indexed(fid)]
        if indexed:
            names = [upload_service.get_file_name(fid, session_id) or fid for fid in indexed]
            names_str = ", ".join(f"'{n}'" for n in names)
            parts.append(
                f"[SYSTEM: The user has uploaded {len(indexed)} document(s) indexed in the "
                f"knowledge base: {names_str}. "
                f"This is a DOCUMENT RESEARCH query (Category C or B+C). "
                f"Delegate to 'Financial Research Analyst' immediately. "
                f"The documents ARE available — do NOT say they are missing.]"
            )
    if ingestion_warnings:
        warn_text = "\n".join(f"- {w}" for w in ingestion_warnings)
        parts.append(f"[SYSTEM WARNING — files that could not be indexed:\n{warn_text}]")
    parts.append(message)
    return "\n\n".join(parts)


async def stream_orchestrator(
    message: str,
    session_id: str,
    attachments: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    SSE streaming pipeline.

    Duplicate-output fix
    ────────────────────
    Agno fires two kinds of content events:
      1. RunResponseDeltaContent — a small new CHUNK (delta) → forward to client
      2. RunResponseContent      — the FULL assembled text  → store only, never forward

    By filtering out snapshot events we prevent the full text from being
    sent twice (once as accumulated deltas, once as a complete snapshot).
    """

    session_kb = create_session_knowledge(session_id)
    ingestion_warnings: list[str] = []
    if attachments:
        loop = asyncio.get_event_loop()
        ingestion_warnings = await loop.run_in_executor(
            None,
            ingestion_service.ingest_files_for_session,
            session_id, attachments, session_kb,
        )

    enriched_message = _build_enriched_message(
        message, attachments, ingestion_warnings, session_id
    )

    research_agent = create_research_agent(session_id)
    team = create_financial_sentinel(research_agent)

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _worker():
        try:
            for ev in team.run(
                enriched_message, stream=True,
                user_id=_USER_ID, session_id=session_id,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, ev)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    fut = loop.run_in_executor(None, _worker)

    # Track the most complete response seen across all agent events
    final_text = ""

    try:
        while True:
            ev = await queue.get()
            if ev is None:
                break
            if isinstance(ev, Exception):
                logger.exception("stream worker error", exc_info=ev)
                yield _sse("error", {"message": str(ev)})
                break

            event_type: str = getattr(ev, "event", "") or ""
            agent_name_ev = getattr(ev, "agent", None) or getattr(ev, "team", None) or ""
            content_ev = getattr(ev, "content", None)
            logger.info("[EVT] type=%r agent=%r content_len=%s content_preview=%r",
                        event_type, agent_name_ev,
                        len(content_ev) if isinstance(content_ev, str) else None,
                        (content_ev or "")[:80] if isinstance(content_ev, str) else None)

            # HITL pause
            if getattr(ev, "is_paused", False):
                agent_run_id, requirements, raw_input, resolved_ticker = _extract_pause_info(ev)
                our_run_id = str(uuid.uuid4())
                _paused_runs[our_run_id] = {
                    "team": team, "run_response": ev,
                    "agent_run_id": agent_run_id, "requirements": requirements,
                    "session_id": session_id, "user_id": _USER_ID,
                }
                yield _sse("hitl", {
                    "run_id": our_run_id, "ticker": resolved_ticker,
                    "raw_input": raw_input,
                    "message": f"🔍 Ticker confirmation: \"{raw_input}\" → **{resolved_ticker}**",
                })
                break

            # Skip noisy internal events
            if event_type in _HIDDEN_EVENT_TYPES:
                continue

            content = getattr(ev, "content", None)
            if content and isinstance(content, str) and content.strip():
                # Fix: In coordinate mode, the Team Leader emits 'TeamRunContent' as tiny delta
                # tokens (length 2-4 bytes). We MUST accumulate them.
                # Member agents emit full snapshots or their own deltas under different event names.
                # Because the Team Leader runs last, we can simply accumulate TeamRunContent.
                if event_type in ("TeamRunContent", "RunResponseDeltaContent", "RunResponseContent"):
                    # If this is a very long string, it might be a snapshot.
                    if len(content) > max(100, len(final_text)):
                        # Only yield what's strictly new if it's a growing snapshot
                        new_part = content[len(final_text):] if content.startswith(final_text) else content
                        final_text = content
                        if new_part:
                            yield _sse("token", {"text": new_part})
                    else:
                        # Failsafe: if the previous text ends with an alphanumeric character
                        # and the new text is a capitalized word (like 'NVDA'), add a space. 
                        # This prevents the "SnapshotA" bug caused by bad LLM tokenization.
                        if final_text and final_text[-1].isalnum() and content and content[0].isupper():
                            final_text += " "
                            yield _sse("token", {"text": " "})
                            
                        final_text += content 
                        yield _sse("token", {"text": content})
                continue

            # Reasoning / thought steps
            reasoning = getattr(ev, "thinking", None) or getattr(ev, "reasoning_content", None)
            if reasoning:
                yield _sse("thought", {"text": reasoning})
                continue

            # Named lifecycle events → emit friendly agent-name labels only
            # We care about: when a member agent STARTS its run (not model-level noise)
            agent_name = getattr(ev, "agent", None) or getattr(ev, "team", None) or ""

            # Emit a thought step when a named agent starts (various Agno event names)
            _AGENT_START_EVENTS = {
                "AgentRunStarted", "TeamMemberAgentStarted", "MemberAgentStarted",
                "Started", "AgentStarted",
            }
            if event_type in _AGENT_START_EVENTS and agent_name:
                yield _sse("thought", {
                    "text": agent_name,
                    "event_type": "AgentRunStarted",
                })
    finally:
        await fut

    yield _sse("done", {"text": final_text})


def _run_orchestrator(team: Team, message: str, session_id: str, user_id: str) -> dict:
    run_response = team.run(message, stream=False, user_id=user_id, session_id=session_id)
    if getattr(run_response, "is_paused", False):
        agent_run_id, requirements, raw_input, resolved_ticker = _extract_pause_info(run_response)
        our_run_id = str(uuid.uuid4())
        _paused_runs[our_run_id] = {
            "team": team, "run_response": run_response,
            "agent_run_id": agent_run_id, "requirements": requirements,
            "session_id": session_id, "user_id": user_id,
        }
        return {"hitl_pending": True, "hitl_ticker": resolved_ticker,
                "hitl_raw_input": raw_input, "hitl_run_id": our_run_id}
    text = getattr(run_response, "content", None) or str(run_response)
    return {"hitl_pending": False, "text": text}


def _resume_orchestrator(run_id: str, confirmed: bool, corrected_ticker: str | None = None) -> dict:
    paused = _paused_runs.pop(run_id, None)
    if not paused:
        return {"hitl_pending": False, "text": "Error: expired or invalid confirmation session."}

    team = paused["team"]
    pause_event = paused["run_response"]
    requirements = paused["requirements"]
    agent_run_id = paused["agent_run_id"]
    session_id = paused["session_id"]
    user_id = paused["user_id"]

    raw_input = ""
    resolved_ticker_val = ""
    for req in requirements:
        if not getattr(req, "needs_confirmation", False):
            continue
        te = getattr(req, "tool_execution", None)
        args = getattr(te, "tool_args", {}) if te else {}
        raw_input = args.get("user_input", "")
        resolved_ticker_val = _resolve_ticker(raw_input)
        if confirmed:
            req.confirm()
        else:
            corrected = (corrected_ticker or "").strip().upper()
            req.reject(note=f"User rejected. Use '{corrected}' instead.")

    ticker_to_use = (
        (corrected_ticker or "").strip().upper() or resolved_ticker_val or raw_input.upper()
    )

    def _try(resumed):
        if getattr(resumed, "is_paused", False):
            nid = str(uuid.uuid4())
            na, nr, nraw, ntick = _extract_pause_info(resumed)
            _paused_runs[nid] = {
                "team": team, "run_response": resumed,
                "agent_run_id": na, "requirements": nr,
                "session_id": session_id, "user_id": user_id,
            }
            return {"hitl_pending": True, "hitl_ticker": ntick,
                    "hitl_raw_input": nraw, "hitl_run_id": nid}
        return {"hitl_pending": False, "text": getattr(resumed, "content", None) or str(resumed)}

    if hasattr(pause_event, "messages") and pause_event.messages is not None:
        try:
            return _try(team.continue_run(
                run_response=pause_event, requirements=requirements,
                stream=False, user_id=user_id, session_id=session_id,
            ))
        except Exception as e:
            logger.warning("team.continue_run failed: %s", e)

    for m in team.members:
        mid = getattr(m, "agent_id", None) or getattr(m, "id", None)
        if str(mid) == str(getattr(pause_event, "agent_id", None)) and agent_run_id:
            try:
                return _try(m.continue_run(
                    run_id=agent_run_id, requirements=requirements,
                    stream=False, user_id=user_id, session_id=session_id,
                ))
            except Exception as e:
                logger.warning("member.continue_run failed: %s", e)
            break

    pre_approve_ticker(ticker_to_use)
    return _try(team.run(
        f"Complete the full financial analysis for {ticker_to_use}.",
        stream=False, user_id=user_id, session_id=session_id,
    ))


async def process_query(
    message: str, session_id: str, attachments: list[str] | None = None
) -> ChatResponse:
    loop = asyncio.get_event_loop()
    session_kb = create_session_knowledge(session_id)
    ingestion_warnings: list[str] = []
    if attachments:
        ingestion_warnings = await loop.run_in_executor(
            None, ingestion_service.ingest_files_for_session,
            session_id, attachments, session_kb,
        )
    enriched = _build_enriched_message(message, attachments, ingestion_warnings, session_id)
    research_agent = create_research_agent(session_id)
    team = create_financial_sentinel(research_agent)
    result = await loop.run_in_executor(None, _run_orchestrator, team, enriched, session_id, _USER_ID)
    if result.get("hitl_pending"):
        return ChatResponse(
            id=str(uuid.uuid4()), text="", hitl_pending=True,
            hitl_ticker=result.get("hitl_ticker", ""),
            hitl_raw_input=result.get("hitl_raw_input", ""),
            hitl_run_id=result.get("hitl_run_id", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    return ChatResponse(
        id=str(uuid.uuid4()), text=result.get("text", ""),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def process_confirm(
    run_id: str, session_id: str, confirmed: bool,
    corrected_ticker: str | None = None,
) -> ChatResponse:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _resume_orchestrator, run_id, confirmed, corrected_ticker,
    )
    if result.get("hitl_pending"):
        return ChatResponse(
            id=str(uuid.uuid4()), text="", hitl_pending=True,
            hitl_ticker=result.get("hitl_ticker", ""),
            hitl_raw_input=result.get("hitl_raw_input", ""),
            hitl_run_id=result.get("hitl_run_id", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    return ChatResponse(
        id=str(uuid.uuid4()), text=result.get("text", ""),
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


confirm_hitl = process_confirm


def clear_team_cache() -> None:
    _paused_runs.clear()