"""Analysis service — bridges the API to the Agno team orchestrator."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from agno.team import Team

from agents.research_agent import create_research_agent, create_session_knowledge
from agents.team_orchestrator import create_financial_sentinel
from schemas.chat_schema import ChatResponse
from services import ingestion_service, upload_service
from tools.market_tool import _resolve_ticker

logger = logging.getLogger(__name__)

_USER_ID = "api_user"

# ── In-memory store for paused runs ──────────────────────────────────
# run_id → { "team": Team, "run_response": RunResponse, "session_id": str }
_paused_runs: dict[str, dict] = {}


def _run_orchestrator(team: Team, message: str, session_id: str, user_id: str) -> dict:
    """
    Run the Agno team synchronously.
    If HITL pauses execution, return the paused state instead of auto-confirming.
    Returns a dict with either final text or HITL pending info.
    """
    run_response = team.run(
        message,
        stream=False,
        user_id=user_id,
        session_id=session_id,
    )

    # Check if the run is paused for HITL
    if hasattr(run_response, "is_paused") and run_response.is_paused:
        requirements = (
            run_response.active_requirements
            if hasattr(run_response, "active_requirements")
            else []
        )

        for req in requirements:
            if hasattr(req, "needs_confirmation") and req.needs_confirmation:
                tool_execution = req.tool_execution
                tool_args = tool_execution.tool_args if tool_execution else {}
                raw_input = tool_args.get("user_input", "")
                resolved_ticker = _resolve_ticker(raw_input)

                # Store paused run
                run_id = str(uuid.uuid4())
                _paused_runs[run_id] = {
                    "team": team,
                    "run_response": run_response,
                    "session_id": session_id,
                    "user_id": user_id,
                }

                return {
                    "hitl_pending": True,
                    "hitl_ticker": resolved_ticker,
                    "hitl_raw_input": raw_input,
                    "hitl_run_id": run_id,
                }

    text = run_response.content if hasattr(run_response, "content") else str(run_response)
    return {"hitl_pending": False, "text": text}


def _resume_orchestrator(run_id: str, confirmed: bool, corrected_ticker: str | None = None) -> dict:
    """
    Resume a paused HITL run after user confirmation/rejection.
    """
    paused = _paused_runs.pop(run_id, None)
    if not paused:
        return {"hitl_pending": False, "text": "Error: expired or invalid confirmation session."}

    team = paused["team"]
    run_response = paused["run_response"]
    session_id = paused["session_id"]
    user_id = paused["user_id"]

    requirements = (
        run_response.active_requirements
        if hasattr(run_response, "active_requirements")
        else []
    )

    for req in requirements:
        if hasattr(req, "needs_confirmation") and req.needs_confirmation:
            if confirmed:
                req.confirm()
            else:
                corrected = (corrected_ticker or "").strip().upper()
                req.reject(
                    note=(
                        f"User rejected the ticker. "
                        f"Use '{corrected}' instead. Call resolve_and_confirm_ticker "
                        f"with user_input='{corrected}' to confirm the new ticker."
                    )
                )

    # Continue the run
    run_response = team.continue_run(
        run_response=run_response,
        requirements=run_response.requirements,
        stream=False,
        user_id=user_id,
        session_id=session_id,
    )

    # Check if HITL pauses again (e.g. user rejected and agent retries)
    if hasattr(run_response, "is_paused") and run_response.is_paused:
        reqs = (
            run_response.active_requirements
            if hasattr(run_response, "active_requirements")
            else []
        )
        for req in reqs:
            if hasattr(req, "needs_confirmation") and req.needs_confirmation:
                tool_execution = req.tool_execution
                tool_args = tool_execution.tool_args if tool_execution else {}
                raw_input = tool_args.get("user_input", "")
                resolved_ticker = _resolve_ticker(raw_input)

                new_run_id = str(uuid.uuid4())
                _paused_runs[new_run_id] = {
                    "team": team,
                    "run_response": run_response,
                    "session_id": session_id,
                    "user_id": user_id,
                }

                return {
                    "hitl_pending": True,
                    "hitl_ticker": resolved_ticker,
                    "hitl_raw_input": raw_input,
                    "hitl_run_id": new_run_id,
                }

    text = run_response.content if hasattr(run_response, "content") else str(run_response)
    return {"hitl_pending": False, "text": text}


async def process_query(
    message: str, session_id: str, attachments: list[str] | None = None
) -> ChatResponse:
    """
    Process a user query through the multi-agent orchestrator.

    Steps:
      1. Create a session-scoped Knowledge / LanceDB table.
      2. Ingest any new PDF attachments into that Knowledge base.
      3. Build a session-scoped research agent + team.
      4. Run the team — if HITL pauses, return confirmation request to frontend.
    """

    # ── 1. Session-scoped knowledge ──────────────────────────────────
    session_kb = create_session_knowledge(session_id)

    # ── 2. Ingest new attachments ────────────────────────────────────
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

    # ── 3. Build enriched prompt ─────────────────────────────────────
    enriched_message = message
    if ingestion_warnings:
        warnings_text = "\n".join(
            f"⚠️ {w}" for w in ingestion_warnings
        )
        enriched_message = (
            f"[System note — some attached files could not be read:\n{warnings_text}]\n\n"
            + message
        )

    # ── 4. Session-scoped agent & team ───────────────────────────────
    research_agent = create_research_agent(session_id)
    team = create_financial_sentinel(research_agent)

    # ── 5. Run orchestrator in thread pool ───────────────────────────
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
            text=f"🔍 Ticker confirmation needed: I resolved **\"{result['hitl_raw_input']}\"** → **{result['hitl_ticker']}**",
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
    """Resume a paused HITL run after user confirmation."""
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
