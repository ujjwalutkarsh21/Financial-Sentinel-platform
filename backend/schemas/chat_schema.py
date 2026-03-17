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
