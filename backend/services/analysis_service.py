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

logger = logging.getLogger(__name__)

_USER_ID = "api_user"


def _run_orchestrator(team: Team, message: str, session_id: str, user_id: str) -> str:
    """
    Run the Agno team synchronously.
    Handles HITL by auto-confirming all ticker requirements.
    """
    run_response = team.run(
        message,
        stream=False,
        user_id=user_id,
        session_id=session_id,
    )

    # Handle HITL auto-confirmation loop
    while hasattr(run_response, "is_paused") and run_response.is_paused:
        requirements = (
            run_response.active_requirements
            if hasattr(run_response, "active_requirements")
            else []
        )

        if not requirements:
            break

        for req in requirements:
            if hasattr(req, "needs_confirmation") and req.needs_confirmation:
                req.confirm()

        run_response = team.continue_run(
            run_response=run_response,
            requirements=run_response.requirements,
            stream=False,
            user_id=user_id,
            session_id=session_id,
        )

    return run_response.content if hasattr(run_response, "content") else str(run_response)


async def process_query(
    message: str, session_id: str, attachments: list[str] | None = None
) -> ChatResponse:
    """
    Process a user query through the multi-agent orchestrator.

    Steps:
      1. Create a session-scoped Knowledge / LanceDB table.
      2. Ingest any new PDF attachments into that Knowledge base.
      3. Build a session-scoped research agent + team.
      4. Run the team in a thread pool so FastAPI's event loop isn't blocked.
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
    text = await loop.run_in_executor(
        None,
        _run_orchestrator,
        team,
        enriched_message,
        session_id,
        _USER_ID,
    )

    return ChatResponse(
        id=str(uuid.uuid4()),
        text=text,
        market_data={},
        news=[],
        sentiment="",
        confidence="",
        sources=[],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
