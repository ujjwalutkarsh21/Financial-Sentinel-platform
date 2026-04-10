"""FastAPI routes for chat, upload, and history."""

import json

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from agents.team_orchestrator import db as agno_db
from schemas.chat_schema import ChatRequest, ChatResponse, UploadResponse, HitlConfirmRequest
from services import analysis_service, upload_service, history_service
from tools.market_tool import clear_all_confirmed_tickers

router = APIRouter(prefix="/api")


@router.get("/stream")
async def stream_query(
    request: Request,
    message: str = Query(...),
    session_id: str = Query(...),
    attachments: str = Query(default=""),
):
    """SSE streaming — pure passthrough, no history logic here."""
    attachment_list = [a for a in attachments.split(",") if a] if attachments else None
    history_service.add_message(session_id, "user", message)

    async def event_generator():
        try:
            async for chunk in analysis_service.stream_orchestrator(
                message=message,
                session_id=session_id,
                attachments=attachment_list,
            ):
                yield chunk
                if await request.is_disconnected():
                    break
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/query", response_model=ChatResponse)
async def query(request: ChatRequest):
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
async def upload(file: UploadFile = File(...), session_id: str = Query(...)):
    try:
        result = await upload_service.save_file(file, session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.get("/history")
async def history(session_id: str = Query(...)):
    return history_service.get_history(session_id)


@router.get("/sessions/{session_id}/files")
async def session_files(session_id: str):
    return upload_service.get_session_files(session_id)


@router.delete("/reset")
async def reset_all():
    history_service.clear()
    upload_service.clear_all_files()
    analysis_service.clear_team_cache()
    clear_all_confirmed_tickers()
    try:
        agno_db.drop()
        agno_db.create()
    except Exception:
        pass
    return {"status": "ok"}


@router.post("/confirm", response_model=ChatResponse)
async def confirm_ticker(request: HitlConfirmRequest):
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
        history_service.add_message(
            request.session_id, "assistant", response.text, response.sources
        )
    return response