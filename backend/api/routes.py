"""FastAPI routes for chat, upload, and history."""

from fastapi import APIRouter, UploadFile, File, HTTPException

from schemas.chat_schema import ChatRequest, ChatResponse, UploadResponse
from services import analysis_service, upload_service, history_service

router = APIRouter(prefix="/api")


@router.post("/query", response_model=ChatResponse)
async def query(request: ChatRequest):
    """Process a chat query through the multi-agent system."""
    # Record user message in history
    history_service.add_message("user", request.message)

    try:
        response = await analysis_service.process_query(
            message=request.message,
            attachments=request.attachments,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Record AI response in history
    history_service.add_message("assistant", response.text, response.sources)

    return response


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    """Upload a file for use in subsequent queries."""
    try:
        result = await upload_service.save_file(file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/history")
async def history():
    """Return the in-memory chat history."""
    return history_service.get_history()
