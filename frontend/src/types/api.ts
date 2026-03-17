// === API request/response types (matches backend Pydantic schemas) ===

export interface ChatRequest {
  message: string;
  attachments?: string[];
}

export interface ChatResponse {
  id: string;
  text: string;
  market_data: Record<string, unknown>;
  news: unknown[];
  sentiment: string;
  confidence: string;
  sources: string[];
  timestamp: string;
}

export interface UploadResponse {
  fileId: string;
  url: string;
  name: string;
}

export interface HistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources: string[];
}
