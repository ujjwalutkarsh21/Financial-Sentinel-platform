// === API request/response types (matches backend Pydantic schemas) ===

export interface ChatRequest {
  message: string;
  session_id: string;
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
  // HITL fields
  hitl_pending?: boolean;
  hitl_ticker?: string;
  hitl_raw_input?: string;
  hitl_run_id?: string;
}

export interface HitlConfirmRequest {
  session_id: string;
  run_id: string;
  confirmed: boolean;
  corrected_ticker?: string;
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
