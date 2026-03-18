// === useChat hook — manages chat state, SSE streaming, and ThoughtTrace ===

import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import * as chatService from '../services/chatService';
import type { Message } from '../types/chat';
import type { ThoughtStep } from '../components/ThoughtTrace';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);   // true while any request is in-flight
  const [isStreaming, setIsStreaming] = useState(false); // true while SSE tokens are flowing
  const [error, setError] = useState<string | null>(null);

  // ── Thought Trace state ────────────────────────────────────────────
  const [thoughtSteps, setThoughtSteps] = useState<ThoughtStep[]>([]);
  const [totalElapsed, setTotalElapsed] = useState<number | undefined>(undefined);
  const [isTraceCollapsed, setIsTraceCollapsed] = useState(false);
  const streamStartRef = useRef<number>(0);

  // ── HITL state ─────────────────────────────────────────────────────
  const [hitlPending, setHitlPending] = useState(false);
  const [hitlTicker, setHitlTicker] = useState('');
  const [hitlRawInput, setHitlRawInput] = useState('');
  const [hitlRunId, setHitlRunId] = useState('');

  // Ref to abort the in-flight SSE stream
  const abortStreamRef = useRef<(() => void) | null>(null);

  // ── helpers ──────────────────────────────────────────────────────────

  /** Map an SSE thought event text to a ThoughtStep icon */
  function iconForThought(text: string, eventType?: string): ThoughtStep['icon'] {
    if (!eventType && !text) return 'brain';
    const t = (eventType ?? text).toLowerCase();
    if (t.includes('search') || t.includes('news') || t.includes('duckduck')) return 'search';
    if (t.includes('data') || t.includes('market') || t.includes('database') || t.includes('db')) return 'database';
    if (t.includes('done') || t.includes('finish') || t.includes('complete') || t.includes('valid')) return 'check';
    if (t.includes('error') || t.includes('fail')) return 'error';
    return 'brain';
  }

  /** Add a new active ThoughtStep and mark the previous one as done */
  function pushThoughtStep(text: string, eventType?: string) {
    setThoughtSteps(prev => {
      const updated = prev.map(s =>
        s.status === 'active' ? { ...s, status: 'done' as const } : s,
      );
      return [
        ...updated,
        {
          id: uuidv4(),
          type: 'thought' as const,
          message: text,
          icon: iconForThought(text, eventType),
          status: 'active' as const,
        },
      ];
    });
  }

  /** Mark all remaining active steps as done */
  function finaliseThoughtSteps() {
    setThoughtSteps(prev =>
      prev.map(s => s.status === 'active' ? { ...s, status: 'done' as const } : s),
    );
  }

  // ── handleResponse — used by non-streaming /confirm path ─────────────

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

  // ── sendStreamingMessage — primary send path via SSE ─────────────────
  // App.tsx calls this as `chat.sendStreamingMessage(...)`

  const sendStreamingMessage = useCallback(
    async (text: string, attachmentIds?: string[]) => {
      if (!text.trim() && (!attachmentIds || attachmentIds.length === 0)) return;

      // Cancel any in-flight stream
      abortStreamRef.current?.();
      abortStreamRef.current = null;

      // Reset thought trace for new message
      setThoughtSteps([]);
      setTotalElapsed(undefined);
      setIsTraceCollapsed(false);
      streamStartRef.current = Date.now();

      // Optimistic user message
      setMessages(prev => [
        ...prev,
        { id: uuidv4(), role: 'user', content: text, timestamp: new Date() },
      ]);

      setIsLoading(true);
      setIsStreaming(true);
      setError(null);
      setHitlPending(false);

      // Placeholder assistant message filled in by tokens
      const assistantId = uuidv4();
      setMessages(prev => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '', timestamp: new Date(), isStreaming: true },
      ]);

      let accumulated = '';

      const abort = chatService.streamMessage(
        text,
        sessionId,
        attachmentIds ?? [],
        {
          onThought: (thoughtText, eventType) => {
            pushThoughtStep(thoughtText, eventType);
          },

          onToken: (chunk) => {
            accumulated += chunk;
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId ? { ...m, content: accumulated, isStreaming: true } : m,
              ),
            );
          },

          onHitl: ({ run_id, ticker, raw_input, message: hitlMsg }) => {
            finaliseThoughtSteps();
            setTotalElapsed((Date.now() - streamStartRef.current) / 1000);
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId ? { ...m, content: hitlMsg, isStreaming: false } : m,
              ),
            );
            setHitlPending(true);
            setHitlTicker(ticker);
            setHitlRawInput(raw_input);
            setHitlRunId(run_id);
            setIsLoading(false);
            setIsStreaming(false);
          },

          onDone: (fullText) => {
            finaliseThoughtSteps();
            setTotalElapsed((Date.now() - streamStartRef.current) / 1000);
            const final = fullText || accumulated;
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId ? { ...m, content: final, isStreaming: false } : m,
              ),
            );
            setIsLoading(false);
            setIsStreaming(false);
            abortStreamRef.current = null;
          },

          onError: (msg) => {
            finaliseThoughtSteps();
            setError(msg);
            setMessages(prev =>
              prev.map(m =>
                m.id === assistantId
                  ? { ...m, content: `⚠️ Error: ${msg}. Please try again.`, isStreaming: false }
                  : m,
              ),
            );
            setIsLoading(false);
            setIsStreaming(false);
            abortStreamRef.current = null;
          },
        },
      );

      abortStreamRef.current = abort;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId],
  );

  // Keep old name as alias so nothing else breaks
  const sendMessage = sendStreamingMessage;

  // ── confirmTicker — REST /confirm path ───────────────────────────────

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
          { id: uuidv4(), role: 'assistant', content: `⚠️ Error: ${errMsg}. Please try again.`, timestamp: new Date() },
        ]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, hitlRunId, handleResponse],
  );

  // ── misc helpers ──────────────────────────────────────────────────────

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
      // best-effort
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
    setThoughtSteps([]);
    setTotalElapsed(undefined);
    setHitlPending(false);
    setIsStreaming(false);
    setIsLoading(false);
  }, []);

  return {
    // Core
    messages,
    setMessages,
    isLoading,
    error,

    // Streaming
    isStreaming,          // used as isAgentStreaming in App.tsx
    sendStreamingMessage, // primary name App.tsx uses
    sendMessage,          // alias

    // Thought Trace — all read by App.tsx
    thoughtSteps,
    totalElapsed,
    isTraceCollapsed,
    setIsTraceCollapsed,

    // HITL
    hitlPending,
    hitlTicker,
    hitlRawInput,
    confirmTicker,

    // Misc
    loadHistory,
    markStreamingComplete,
    clearMessages,
  };
}