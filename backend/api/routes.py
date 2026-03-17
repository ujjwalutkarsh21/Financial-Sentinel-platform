"""FastAPI routes for chat, upload, and history."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query

from schemas.chat_schema import ChatRequest, ChatResponse, UploadResponse
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
