// === useChat hook — manages chat state and SSE streaming, scoped by session ===

import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import * as chatService from '../services/chatService';
import type { Message } from '../types/chat';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // HITL state
  const [hitlPending, setHitlPending] = useState(false);
  const [hitlTicker, setHitlTicker] = useState('');
  const [hitlRawInput, setHitlRawInput] = useState('');
  const [hitlRunId, setHitlRunId] = useState('');

  // Ref to abort the in-flight SSE stream (e.g. on component unmount or new message)
  const abortStreamRef = useRef<(() => void) | null>(null);

  // ── helpers ───────────────────────────────────────────────────────

  /** Handle a non-streaming ChatResponse (used by /confirm fallback) */
  const handleResponse = useCallback((response: any) => {
    if (response.hitl_pending) {
      setHitlPending(true);
      setHitlTicker(response.hitl_ticker || '');
      setHitlRawInput(response.hitl_raw_input || '');
      setHitlRunId(response.hitl_run_id || '');
      setMessages(prev => [
        ...prev,
        {
          id: response.id ?? uuidv4(),
          role: 'assistant',
          content: response.text,
          timestamp: new Date(response.timestamp ?? Date.now()),
        },
      ]);
    } else {
      setHitlPending(false);
      setMessages(prev => [
        ...prev,
        {
          id: response.id ?? uuidv4(),
          role: 'assistant',
          content: response.text,
          timestamp: new Date(response.timestamp ?? Date.now()),
          sources: response.sources,
          isStreaming: false,
        },
      ]);
    }
  }, []);

  // ── sendMessage — uses SSE stream ─────────────────────────────────

  const sendMessage = useCallback(
    async (text: string, attachmentIds?: string[]) => {
      if (!text.trim() && (!attachmentIds || attachmentIds.length === 0)) return;

      // Cancel any in-flight stream
      abortStreamRef.current?.();
      abortStreamRef.current = null;

      // Optimistic user message
      const userMessage: Message = {
        id: uuidv4(),
        role: 'user',
        content: text,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);
      setHitlPending(false);

      // Placeholder assistant message that we'll fill in via tokens
      const assistantId = uuidv4();
      setMessages(prev => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        },
      ]);

      // Accumulate streamed tokens
      let accumulated = '';

      const abort = chatService.streamMessage(
        text,
        sessionId,
        attachmentIds ?? [],
        {
          // Thought trace events — update a separate "thoughts" field if your
          // UI uses it; if not, they're safely ignored here.
          onThought: (_thought) => {
            // Thought trace UI reads from a separate state/component;
            // if you want to surface it in-message you can extend Message
            // to include a `thoughts` array and push here.
          },

          onToken: (chunk) => {
            accumulated += chunk;
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: accumulated, isStreaming: true }
                  : m,
              ),
            );
          },

          onHitl: ({ run_id, ticker, raw_input, message: hitlMsg }) => {
            // Replace placeholder with HITL info message, then surface confirm UI
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: hitlMsg, isStreaming: false }
                  : m,
              ),
            );
            setHitlPending(true);
            setHitlTicker(ticker);
            setHitlRawInput(raw_input);
            setHitlRunId(run_id);
            setIsLoading(false);
          },

          onDone: (fullText) => {
            // Finalise the message — use accumulated tokens as canonical text
            const final = fullText || accumulated;
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: final, isStreaming: false }
                  : m,
              ),
            );
            setIsLoading(false);
            abortStreamRef.current = null;
          },

          onError: (msg) => {
            setError(msg);
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? {
                    ...m,
                    content: `⚠️ Error: ${msg}. Please try again.`,
                    isStreaming: false,
                  }
                  : m,
              ),
            );
            setIsLoading(false);
            abortStreamRef.current = null;
          },
        },
      );

      abortStreamRef.current = abort;
    },
    [sessionId],
  );

  // ── confirmTicker — calls REST /confirm, not SSE ──────────────────

  const confirmTicker = useCallback(
    async (confirmed: boolean, correctedTicker?: string) => {
      if (!hitlRunId) return;

      setIsLoading(true);
      setHitlPending(false);

      try {
        const response = await chatService.confirmTicker({
          session_id: sessionId,
          run_id: hitlRunId,
          confirmed,
          corrected_ticker: correctedTicker,
        });
        handleResponse(response);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Confirmation failed';
        setError(errMsg);
        setMessages(prev => [
          ...prev,
          {
            id: uuidv4(),
            role: 'assistant',
            content: `⚠️ Error: ${errMsg}. Please try again.`,
            timestamp: new Date(),
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, hitlRunId, handleResponse],
  );

  // ── misc helpers ──────────────────────────────────────────────────

  const loadHistory = useCallback(async () => {
    try {
      const history = await chatService.getHistory(sessionId);
      setMessages(
        history.map(h => ({
          id: h.id,
          role: h.role as 'user' | 'assistant',
          content: h.content,
          timestamp: new Date(h.timestamp),
          sources: h.sources,
        })),
      );
    } catch {
      // Silently fail — history is best-effort
    }
  }, [sessionId]);

  const markStreamingComplete = useCallback((messageId: string) => {
    setMessages(prev =>
      prev.map(m => (m.id === messageId ? { ...m, isStreaming: false } : m)),
    );
  }, []);

  const clearMessages = useCallback(() => {
    abortStreamRef.current?.();
    abortStreamRef.current = null;
    setMessages([]);
    setHitlPending(false);
  }, []);

  return {
    messages,
    setMessages,
    isLoading,
    error,
    sendMessage,
    loadHistory,
    markStreamingComplete,
    clearMessages,
    // HITL
    hitlPending,
    hitlTicker,
    hitlRawInput,
    confirmTicker,
  };
}