"""Analysis service — bridges the API to the Agno team orchestrator."""

import asyncio
import uuid
from datetime import datetime, timezone

from agents.team_orchestrator import financial_sentinel
from schemas.chat_schema import ChatResponse
from services import upload_service

_USER_ID = "api_user"


def _run_orchestrator(message: str, session_id: str, user_id: str) -> str:
    """
    Run the Agno team synchronously.
    Handles HITL by auto-confirming all ticker requirements.
    """
    run_response = financial_sentinel.run(
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

        run_response = financial_sentinel.continue_run(
            run_response=run_response,
            requirements=run_response.requirements,
            stream=False,
            user_id=user_id,
            session_id=session_id,
        )

    return run_response.content if hasattr(run_response, "content") else str(run_response)


async def process_query(message: str, session_id: str, attachments: list[str] | None = None) -> ChatResponse:
    """
    Process a user query through the multi-agent orchestrator.

    Runs the synchronous Agno team in a thread pool so the FastAPI
    event loop isn't blocked.
    """
    # If attachments are present, prepend context about them
    enriched_message = message
    if attachments:
        file_info = []
        for file_id in attachments:
            path = upload_service.get_file_path(file_id, session_id)
            if path:
                file_info.append(f"[Attached file: {path}]")
        if file_info:
            enriched_message = "\n".join(file_info) + "\n\n" + message

    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(
        None,
        _run_orchestrator,
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
