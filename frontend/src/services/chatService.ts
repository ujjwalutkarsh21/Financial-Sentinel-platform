// === Chat service — backend endpoint wrappers ===

import { post, get, upload } from './api';
import type { ChatRequest, ChatResponse, UploadResponse, HistoryMessage } from '../types/api';

export async function sendMessage(data: ChatRequest): Promise<ChatResponse> {
  return post<ChatResponse>('/api/query', data);
}

export async function uploadFile(file: File, sessionId: string): Promise<UploadResponse> {
  return upload<UploadResponse>(`/api/upload?session_id=${encodeURIComponent(sessionId)}`, file);
}

export async function getHistory(sessionId: string): Promise<HistoryMessage[]> {
  return get<HistoryMessage[]>(`/api/history?session_id=${encodeURIComponent(sessionId)}`);
}
