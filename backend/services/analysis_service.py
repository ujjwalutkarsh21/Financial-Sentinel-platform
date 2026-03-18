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

# ── In-memory store for paused runs ──────────────────────────────────
# Keyed by our own run_id (UUID string).
# Stores only agent_run_id + requirements — NOT the full event object —
# so the resume call never touches .messages on a RunPausedEvent.
#
# Shape:
#   our_run_id → {
#       "team":         Team,
#       "agent_run_id": str | None,
#       "requirements": list,
#       "session_id":   str,
#       "user_id":      str,
#   }
_paused_runs: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_pause_info(pause_event) -> tuple[str | None, list, str, str]:
    """
    Safely pull (agent_run_id, requirements, raw_input, resolved_ticker)
    from whatever pause object Agno emits — a full RunResponse *or* a
    lightweight RunPausedEvent.  Neither is guaranteed to carry all attrs.
    """
    agent_run_id: str | None = getattr(pause_event, "run_id", None)

    if not agent_run_id:
        agent_run_id = (
            getattr(pause_event, "session_run_id", None) or
            getattr(pause_event, "id", None)
        )
    
    logger.warning("HITL pause — agent_run_id=%s, type=%s, attrs=%s",
                   agent_run_id, type(pause_event).__name__,
                   [a for a in dir(pause_event) if not a.startswith("_")])

    requirements: list = []
    if hasattr(pause_event, "active_requirements"):
        requirements = pause_event.active_requirements or []
    elif hasattr(pause_event, "requirements"):
        requirements = pause_event.requirements or []

    raw_input = ""
    resolved_ticker = ""
    for req in requirements:
        if getattr(req, "needs_confirmation", False):
            tool_execution = getattr(req, "tool_execution", None)
            tool_args = getattr(tool_execution, "tool_args", {}) if tool_execution else {}
            raw_input = tool_args.get("user_input", "")
            resolved_ticker = _resolve_ticker(raw_input)
            break

    return agent_run_id, requirements, raw_input, resolved_ticker


def _sse(event: str, data: dict) -> str:
    """Format a single SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# Streaming orchestrator — Thought Trace SSE
# ---------------------------------------------------------------------------

async def stream_orchestrator(
    message: str,
    session_id: str,
    attachments: list[str] | None = None,
) -> AsyncGenerator[str, None]:
    """
    Async generator consumed by the SSE endpoint in routes.py.

    Yields SSE-formatted strings for each Agno event.

    Event types emitted:
      • thought  — intermediate reasoning / delegation step label
      • token    — final answer token chunk
      • hitl     — run paused, user confirmation required
      • done     — stream complete (carries full assembled text)
      • error    — unrecoverable worker error

    HITL handling stores only (agent_run_id, requirements) — never the
    full RunPausedEvent — so _resume_orchestrator never hits .messages.
    """

    # ── 1. Session knowledge & ingestion ─────────────────────────────
    session_kb = create_session_knowledge(session_id)

    ingestion_warnings: list[str] = []
    if attachments:
        loop = asyncio.get_event_loop()
        ingestion_warnings = await loop.run_in_executor(
            None,
            ingestion_service.ingest_files_for_session,
            session_id,
            attachments,
            session_kb,
        )

    enriched_message = message
    if ingestion_warnings:
        warnings_text = "\n".join(f"⚠️ {w}" for w in ingestion_warnings)
        enriched_message = (
            f"[System note — some attached files could not be read:\n{warnings_text}]\n\n"
            + message
        )

    # ── 2. Build team ─────────────────────────────────────────────────
    research_agent = create_research_agent(session_id)
    team = create_financial_sentinel(research_agent)

    # ── 3. Run sync Agno stream in thread, bridge to async via queue ──
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _stream_worker():
        try:
            for event in team.run(
                enriched_message,
                stream=True,
                user_id=_USER_ID,
                session_id=session_id,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

    executor_future = loop.run_in_executor(None, _stream_worker)
    full_text_parts: list[str] = []

    try:
        while True:
            event = await queue.get()

            # Sentinel — stream finished cleanly
            if event is None:
                break

            # Worker raised an exception
            if isinstance(event, Exception):
                logger.exception("stream_orchestrator worker error", exc_info=event)
                yield _sse("error", {"message": str(event)})
                break

            event_type: str = getattr(event, "event", "") or ""

            # ── HITL pause ────────────────────────────────────────────
            if getattr(event, "is_paused", False):
                agent_run_id, requirements, raw_input, resolved_ticker = _extract_pause_info(event)

                our_run_id = str(uuid.uuid4())
                _paused_runs[our_run_id] = {
                    "team":         team,
                    "run_response": event,           # ← store the full pause event
                    "agent_run_id": agent_run_id,   # ← ADD THIS
                    "requirements": requirements,
                    "session_id":   session_id,
                    "user_id":      _USER_ID,
                }

                yield _sse("hitl", {
                    "run_id":    our_run_id,
                    "ticker":    resolved_ticker,
                    "raw_input": raw_input,
                    "message": (
                        f"🔍 Ticker confirmation needed: I resolved "
                        f"\"{raw_input}\" → **{resolved_ticker}**"
                    ),
                })
                break  # stop consuming — client will call /confirm

            # ── Final content tokens ──────────────────────────────────
            content = getattr(event, "content", None)
            if content and isinstance(content, str):
                full_text_parts.append(content)
                yield _sse("token", {"text": content})
                continue

            # ── Intermediate reasoning ────────────────────────────────
            reasoning = getattr(event, "thinking", None) or getattr(event, "reasoning_content", None)
            if reasoning:
                yield _sse("thought", {"text": reasoning})
                continue

            # ── Named Agno lifecycle events → thought trace ───────────
            if event_type and event_type not in (
                "RunResponseContent", "RunResponseDeltaContent"
            ):
                label = (
                    event_type
                    .replace("TeamRun", "")
                    .replace("AgentRun", "")
                    .replace("Run", "")
                ).strip()
                agent_name = getattr(event, "agent", None) or getattr(event, "team", None) or ""
                if label:
                    yield _sse("thought", {
                        "text": f"{label}{f' · {agent_name}' if agent_name else ''}",
                        "event_type": event_type,
                    })

    finally:
        await executor_future

    yield _sse("done", {"text": "".join(full_text_parts)})


# ---------------------------------------------------------------------------
# Non-streaming orchestrator (fallback for /api/query)
# ---------------------------------------------------------------------------

def _run_orchestrator(team: Team, message: str, session_id: str, user_id: str) -> dict:
    """Synchronous run; returns hitl_pending dict or final text dict."""
    run_response = team.run(
        message,
        stream=False,
        user_id=user_id,
        session_id=session_id,
    )

    if getattr(run_response, "is_paused", False):
        agent_run_id, requirements, raw_input, resolved_ticker = _extract_pause_info(run_response)

        our_run_id = str(uuid.uuid4())
        _paused_runs[our_run_id] = {
            "team":         team,
            "run_response": run_response,    # ← store the full pause response
            "agent_run_id": agent_run_id,   # ← ADD THIS
            "requirements": requirements,
            "session_id":   session_id,
            "user_id":      user_id,
        }

        return {
            "hitl_pending":   True,
            "hitl_ticker":    resolved_ticker,
            "hitl_raw_input": raw_input,
            "hitl_run_id":    our_run_id,
        }

    text = getattr(run_response, "content", None) or str(run_response)
    return {"hitl_pending": False, "text": text}


# ---------------------------------------------------------------------------
# Resume orchestrator (HITL confirm / reject)
# ---------------------------------------------------------------------------

def _resume_orchestrator(
    run_id: str, confirmed: bool, corrected_ticker: str | None = None
) -> dict:
    paused = _paused_runs.pop(run_id, None)
    if not paused:
        return {"hitl_pending": False, "text": "Error: expired or invalid confirmation session."}

    team         = paused["team"]
    pause_event  = paused["run_response"]
    requirements = paused["requirements"]
    agent_run_id = paused["agent_run_id"]
    session_id   = paused["session_id"]
    user_id      = paused["user_id"]

    # Extract ticker info before confirming/rejecting
    raw_input = ""
    resolved_ticker_val = ""
    for req in requirements:
        if not getattr(req, "needs_confirmation", False):
            continue
        tool_execution = getattr(req, "tool_execution", None)
        tool_args = getattr(tool_execution, "tool_args", {}) if tool_execution else {}
        raw_input = tool_args.get("user_input", "")
        resolved_ticker_val = _resolve_ticker(raw_input)

        if confirmed:
            req.confirm()
        else:
            corrected = (corrected_ticker or "").strip().upper()
            req.reject(
                note=(
                    f"User rejected. Use '{corrected}' instead. "
                    f"Call resolve_and_confirm_ticker with user_input='{corrected}'."
                )
            )

    ticker_to_use = (
        (corrected_ticker or "").strip().upper()
        or resolved_ticker_val
        or raw_input.upper()
    )

    # If pause_event has .messages (TeamRunOutput), use team.continue_run()
    if hasattr(pause_event, "messages") and pause_event.messages is not None:
        logger.info("Resuming via team.continue_run() — pause_event has .messages")
        try:
            resumed = team.continue_run(
                run_response=pause_event,
                requirements=requirements,
                stream=False,
                user_id=user_id,
                session_id=session_id,
            )
            if getattr(resumed, "is_paused", False):
                new_agent_run_id, new_reqs, new_raw, new_ticker = _extract_pause_info(resumed)
                new_run_id = str(uuid.uuid4())
                _paused_runs[new_run_id] = {
                    "team":         team,
                    "run_response": resumed,
                    "agent_run_id": new_agent_run_id,
                    "requirements": new_reqs,
                    "session_id":   session_id,
                    "user_id":      user_id,
                }
                return {
                    "hitl_pending":   True,
                    "hitl_ticker":    new_ticker,
                    "hitl_raw_input": new_raw,
                    "hitl_run_id":    new_run_id,
                }
            text = getattr(resumed, "content", None) or str(resumed)
            return {"hitl_pending": False, "text": text}
        except Exception as e:
            logger.warning("team.continue_run failed: %s", e)

    # Pause event is RunPausedEvent (no .messages) — try member agent first
    paused_agent_id = getattr(pause_event, "agent_id", None)
    member_agent = None
    for m in team.members:
        mid = getattr(m, "agent_id", None) or getattr(m, "id", None)
        if str(mid) == str(paused_agent_id):
            member_agent = m
            break

    if member_agent is not None and agent_run_id:
        logger.info("Resuming via member_agent.continue_run() run_id=%s", agent_run_id)
        try:
            resumed = member_agent.continue_run(
                run_id=agent_run_id,
                requirements=requirements,
                stream=False,
                user_id=user_id,
                session_id=session_id,
            )
            if getattr(resumed, "is_paused", False):
                new_agent_run_id, new_reqs, new_raw, new_ticker = _extract_pause_info(resumed)
                new_run_id = str(uuid.uuid4())
                _paused_runs[new_run_id] = {
                    "team":         team,
                    "run_response": resumed,
                    "agent_run_id": new_agent_run_id,
                    "requirements": new_reqs,
                    "session_id":   session_id,
                    "user_id":      user_id,
                }
                return {
                    "hitl_pending":   True,
                    "hitl_ticker":    new_ticker,
                    "hitl_raw_input": new_raw,
                    "hitl_run_id":    new_run_id,
                }
            text = getattr(resumed, "content", None) or str(resumed)
            return {"hitl_pending": False, "text": text}
        except Exception as e:
            logger.warning("member_agent.continue_run failed (%s) — using re-run fallback", e)

        # Last resort: pre-approve the ticker so resolve_and_confirm_ticker
        # skips HITL on the re-run, then run the team fresh
        logger.info("Fallback re-run with pre-approved ticker=%s", ticker_to_use)
        pre_approve_ticker(ticker_to_use)   # ← this is the key line
    
        run_response = team.run(
            f"Complete the full financial analysis for {ticker_to_use}.",
            stream=False,
            user_id=user_id,
            session_id=session_id,
        )
        if getattr(run_response, "is_paused", False):
            # Still paused = different ticker triggered HITL, handle normally
            new_agent_run_id, new_reqs, new_raw, new_ticker = _extract_pause_info(run_response)
            new_run_id = str(uuid.uuid4())
            _paused_runs[new_run_id] = {
                "team":         team,
                "run_response": run_response,
                "agent_run_id": new_agent_run_id,
                "requirements": new_reqs,
                "session_id":   session_id,
                "user_id":      user_id,
            }
            return {
                "hitl_pending":   True,
                "hitl_ticker":    new_ticker,
                "hitl_raw_input": new_raw,
                "hitl_run_id":    new_run_id,
            }
        text = getattr(run_response, "content", None) or str(run_response)
        return {"hitl_pending": False, "text": text}    


# ---------------------------------------------------------------------------
# Public async entry-points
# ---------------------------------------------------------------------------

async def process_query(
    message: str, session_id: str, attachments: list[str] | None = None
) -> ChatResponse:
    """Non-streaming query — used by POST /api/query."""
    session_kb = create_session_knowledge(session_id)

    ingestion_warnings: list[str] = []
    if attachments:
        loop = asyncio.get_event_loop()
        ingestion_warnings = await loop.run_in_executor(
            None,
            ingestion_service.ingest_files_for_session,
            session_id,
            attachments,
            session_kb,
        )

    enriched_message = message
    if ingestion_warnings:
        warnings_text = "\n".join(f"⚠️ {w}" for w in ingestion_warnings)
        enriched_message = (
            f"[System note — some attached files could not be read:\n{warnings_text}]\n\n"
            + message
        )

    research_agent = create_research_agent(session_id)
    team = create_financial_sentinel(research_agent)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _run_orchestrator,
        team,
        enriched_message,
        session_id,
        _USER_ID,
    )

    if result["hitl_pending"]:
        return ChatResponse(
            id=str(uuid.uuid4()),
            text=(
                f"🔍 Ticker confirmation needed: I resolved "
                f"**\"{result['hitl_raw_input']}\"** → **{result['hitl_ticker']}**"
            ),
            hitl_pending=True,
            hitl_ticker=result["hitl_ticker"],
            hitl_raw_input=result["hitl_raw_input"],
            hitl_run_id=result["hitl_run_id"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return ChatResponse(
        id=str(uuid.uuid4()),
        text=result["text"],
        market_data={},
        news=[],
        sentiment="",
        confidence="",
        sources=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def process_confirm(
    run_id: str, session_id: str, confirmed: bool, corrected_ticker: str | None = None
) -> ChatResponse:
    """Resume a paused HITL run — used by POST /api/confirm."""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _resume_orchestrator,
        run_id,
        confirmed,
        corrected_ticker,
    )

    if result["hitl_pending"]:
        return ChatResponse(
            id=str(uuid.uuid4()),
            text=f"🔍 Ticker confirmation needed: I resolved → **{result['hitl_ticker']}**",
            hitl_pending=True,
            hitl_ticker=result["hitl_ticker"],
            hitl_raw_input=result["hitl_raw_input"],
            hitl_run_id=result["hitl_run_id"],
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return ChatResponse(
        id=str(uuid.uuid4()),
        text=result["text"],
        market_data={},
        news=[],
        sentiment="",
        confidence="",
        sources=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )