from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    message: str
    session_id: str
    attachments: Optional[list[str]] = None


class ChatResponse(BaseModel):
    id: str
    text: str
    market_data: dict = {}
    news: list = []
    sentiment: str = ""
    confidence: str = ""
    sources: list = []
    timestamp: str = ""
    # ── HITL fields ──
    hitl_pending: bool = False
    hitl_ticker: str = ""
    hitl_raw_input: str = ""
    hitl_run_id: str = ""


class HitlConfirmRequest(BaseModel):
    session_id: str
    run_id: str
    confirmed: bool
    corrected_ticker: Optional[str] = None


class UploadResponse(BaseModel):
    fileId: str
    url: str
    name: str


class HistoryMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    sources: list = []
