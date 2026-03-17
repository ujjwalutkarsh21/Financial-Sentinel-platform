"""FastAPI routes for chat, upload, and history."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query

from schemas.chat_schema import ChatRequest, ChatResponse, UploadResponse, HitlConfirmRequest
from services import analysis_service, upload_service, history_service

router = APIRouter(prefix="/api")


@router.post("/query", response_model=ChatResponse)
async def query(request: ChatRequest):
    """Process a chat query through the multi-agent system."""
    session_id = request.session_id

    # Record user message in session-scoped history
    history_service.add_message(session_id, "user", request.message)

    try:
        response = await analysis_service.process_query(
            message=request.message,
            session_id=session_id,
            attachments=request.attachments,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Record AI response in session-scoped history
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
    """
    Wipe ALL server-side state: chat history, uploaded files (disk + registry),
    indexed-files tracking, and Agno's SQLite memory.
    Called by the frontend "Exit" button.
    """
    # 1. Clear chat history
    history_service.clear()

    # 2. Clear uploads (registry + disk files)
    upload_service.clear_all_files()

    # 3. Clear the Agno SQLite memory DB
    try:
        from agents.team_orchestrator import db as agno_db
        agno_db.clear()
    except Exception:
        pass  # best-effort

    return {"status": "ok"}


@router.post("/confirm", response_model=ChatResponse)
async def confirm_ticker(request: HitlConfirmRequest):
    """
    Accept or reject a HITL ticker confirmation and resume the paused run.
    """
    try:
        response = await analysis_service.process_confirm(
            run_id=request.run_id,
            session_id=request.session_id,
            confirmed=request.confirmed,
            corrected_ticker=request.corrected_ticker,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Record AI response in history
    if not response.hitl_pending:
        history_service.add_message(request.session_id, "assistant", response.text, response.sources)

    return response
