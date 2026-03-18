// === Chat service — backend endpoint wrappers ===

import { post, get, upload } from './api';
import type { ChatRequest, ChatResponse, UploadResponse, HistoryMessage, HitlConfirmRequest } from '../types/api';

const BASE_URL = import.meta.env.VITE_API_URL || '';

// ---------------------------------------------------------------------------
// SSE streaming — connects to GET /api/stream
// ---------------------------------------------------------------------------

export interface StreamCallbacks {
  onThought?: (text: string, eventType?: string) => void;
  onToken?: (text: string) => void;
  onHitl?: (data: { run_id: string; ticker: string; raw_input: string; message: string }) => void;
  onDone?: (fullText: string) => void;
  onError?: (message: string) => void;
}

/**
 * Open an SSE connection to /api/stream and dispatch events to callbacks.
 * Returns a cleanup function that aborts the connection.
 */
export function streamMessage(
  message: string,
  sessionId: string,
  attachmentIds: string[] = [],
  callbacks: StreamCallbacks = {},
): () => void {
  const params = new URLSearchParams({
    message,
    session_id: sessionId,
    attachments: attachmentIds.join(','),
  });

  const url = `${BASE_URL}/api/stream?${params.toString()}`;
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { Accept: 'text/event-stream' },
      });

      if (!response.ok) {
        const text = await response.text();
        callbacks.onError?.(`HTTP ${response.status}: ${text}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        callbacks.onError?.('No response body');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by double newlines
        const frames = buffer.split('\n\n');
        // Keep the last (possibly incomplete) chunk in the buffer
        buffer = frames.pop() ?? '';

        for (const frame of frames) {
          if (!frame.trim()) continue;

          let eventType = 'message';
          let data = '';

          for (const line of frame.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              data = line.slice(6).trim();
            }
          }

          if (!data) continue;

          let parsed: Record<string, unknown> = {};
          try {
            parsed = JSON.parse(data);
          } catch {
            continue;
          }

          switch (eventType) {
            case 'thought':
              callbacks.onThought?.(
                String(parsed.text ?? ''),
                parsed.event_type as string | undefined,
              );
              break;

            case 'token':
              callbacks.onToken?.(String(parsed.text ?? ''));
              break;

            case 'hitl':
              callbacks.onHitl?.({
                run_id: String(parsed.run_id ?? ''),
                ticker: String(parsed.ticker ?? ''),
                raw_input: String(parsed.raw_input ?? ''),
                message: String(parsed.message ?? ''),
              });
              break;

            case 'done':
              callbacks.onDone?.(String(parsed.text ?? ''));
              break;

            case 'error':
              callbacks.onError?.(String(parsed.message ?? 'Unknown stream error'));
              break;

            default:
              break;
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        callbacks.onError?.(err instanceof Error ? err.message : 'Stream failed');
      }
    }
  })();

  // Return abort handle so caller can cancel (e.g. component unmount)
  return () => controller.abort();
}

// ---------------------------------------------------------------------------
// REST endpoints
// ---------------------------------------------------------------------------

export async function sendMessage(data: ChatRequest): Promise<ChatResponse> {
  return post<ChatResponse>('/api/query', data);
}

export async function uploadFile(file: File, sessionId: string): Promise<UploadResponse> {
  return upload<UploadResponse>(`/api/upload?session_id=${encodeURIComponent(sessionId)}`, file);
}

export async function getHistory(sessionId: string): Promise<HistoryMessage[]> {
  return get<HistoryMessage[]>(`/api/history?session_id=${encodeURIComponent(sessionId)}`);
}

export async function confirmTicker(data: HitlConfirmRequest): Promise<ChatResponse> {
  return post<ChatResponse>('/api/confirm', data);
}

export async function resetSession(): Promise<void> {
  await fetch('/api/reset', { method: 'DELETE' });
}