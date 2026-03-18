"""FastAPI routes for chat, upload, and history."""

import asyncio
import json

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from agents.team_orchestrator import db as agno_db
from schemas.chat_schema import ChatRequest, ChatResponse, UploadResponse, HitlConfirmRequest
from services import analysis_service, upload_service, history_service

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# SSE streaming endpoint — used by the Thought Trace UI
# ---------------------------------------------------------------------------

@router.get("/stream")
async def stream_query(
    request: Request,
    message: str = Query(...),
    session_id: str = Query(...),
    attachments: str = Query(default=""),   # comma-separated file IDs or empty
):
    """
    Server-Sent Events endpoint.  The frontend connects here for streaming
    responses; we forward each Agno event as an SSE frame.

    Event types: thought | token | hitl | done | error
    """
    attachment_list = [a for a in attachments.split(",") if a] if attachments else None

    # Record user message in history (same as the non-streaming /query does)
    history_service.add_message(session_id, "user", message)

    async def event_generator():
        full_text_parts: list[str] = []
        try:
            async for chunk in analysis_service.stream_orchestrator(
                message=message,
                session_id=session_id,
                attachments=attachment_list,
            ):
                # Collect final text so we can persist it after streaming
                try:
                    frame = chunk  # already an "event: X\ndata: {...}\n\n" string
                    # Extract event type and data for history recording
                    lines = frame.strip().split("\n")
                    ev_type = ""
                    ev_data = {}
                    for line in lines:
                        if line.startswith("event: "):
                            ev_type = line[7:]
                        elif line.startswith("data: "):
                            try:
                                ev_data = json.loads(line[6:])
                            except Exception:
                                pass
                    if ev_type == "token":
                        full_text_parts.append(ev_data.get("text", ""))
                    elif ev_type == "done":
                        # done frame carries the complete assembled text
                        full_text = ev_data.get("text", "".join(full_text_parts))
                        if full_text:
                            history_service.add_message(session_id, "assistant", full_text, [])
                except Exception:
                    pass  # never let history parsing break the stream

                yield chunk

                # Check if client disconnected
                if await request.is_disconnected():
                    break

        except Exception as exc:
            error_frame = f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            yield error_frame

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",       # disables nginx buffering
            "Connection": "keep-alive",
        },
    )


# ---------------------------------------------------------------------------
# Non-streaming fallback — kept for compatibility / HITL confirm flow
# ---------------------------------------------------------------------------

@router.post("/query", response_model=ChatResponse)
async def query(request: ChatRequest):
    """Non-streaming query — fallback if SSE is unavailable."""
    session_id = request.session_id
    history_service.add_message(session_id, "user", request.message)

    try:
        response = await analysis_service.process_query(
            message=request.message,
            session_id=session_id,
            attachments=request.attachments,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    history_service.add_message(session_id, "assistant", response.text, response.sources)
    return response


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    session_id: str = Query(..., description="Session ID to scope the upload to"),
):
    """Upload a file for use in subsequent queries."""
    try:
        result = await upload_service.save_file(file, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/history")
async def history(session_id: str = Query(..., description="Session ID to retrieve history for")):
    """Return the chat history for a specific session."""
    return history_service.get_history(session_id)


@router.get("/sessions/{session_id}/files")
async def session_files(session_id: str):
    """Return all uploaded files for a session."""
    return upload_service.get_session_files(session_id)


@router.delete("/reset")
async def reset_all():
    """Wipe ALL server-side state. Called by the frontend Exit button."""
    history_service.clear()
    upload_service.clear_all_files()
    try:
        agno_db.clear()
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/confirm", response_model=ChatResponse)
async def confirm_ticker(request: HitlConfirmRequest):
    """Accept or reject a HITL ticker confirmation and resume the paused run."""
    try:
        response = await analysis_service.process_confirm(
            run_id=request.run_id,
            session_id=request.session_id,
            confirmed=request.confirmed,
            corrected_ticker=request.corrected_ticker,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not response.hitl_pending:
        history_service.add_message(request.session_id, "assistant", response.text, response.sources)

    return response