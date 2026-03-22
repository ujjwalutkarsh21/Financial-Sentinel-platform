// frontend/src/hooks/useChat.ts
import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import * as chatService from '../services/chatService';
import type { Message } from '../types/chat';
import type { ThoughtStep } from '../components/ThoughtTrace';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [thoughtSteps, setThoughtSteps] = useState<ThoughtStep[]>([]);
  const [totalElapsed, setTotalElapsed] = useState<number | undefined>(undefined);
  const [isTraceCollapsed, setIsTraceCollapsed] = useState(false);
  const streamStartRef = useRef<number>(0);

  const [hitlPending, setHitlPending] = useState(false);
  const [hitlTicker, setHitlTicker] = useState('');
  const [hitlRawInput, setHitlRawInput] = useState('');
  const [hitlRunId, setHitlRunId] = useState('');

  const abortStreamRef = useRef<(() => void) | null>(null);
  // true once onDone/onHitl/onError fires — blocks any stale onToken callbacks
  const doneRef = useRef(false);

  function iconForThought(text: string, eventType?: string): ThoughtStep['icon'] {
    const t = (eventType ?? text).toLowerCase();
    if (t.includes('search') || t.includes('news') || t.includes('duckduck')) return 'search';
    if (t.includes('data') || t.includes('market') || t.includes('database')) return 'database';
    if (t.includes('done') || t.includes('finish') || t.includes('complete') || t.includes('valid')) return 'check';
    if (t.includes('error') || t.includes('fail')) return 'error';
    return 'brain';
  }

  function pushThoughtStep(text: string, eventType?: string) {
    setThoughtSteps(prev => [
      ...prev.map(s => s.status === 'active' ? { ...s, status: 'done' as const } : s),
      {
        id: uuidv4(), type: 'thought' as const,
        message: text, icon: iconForThought(text, eventType),
        status: 'active' as const,
      },
    ]);
  }

  function finaliseThoughtSteps() {
    setThoughtSteps(prev =>
      prev.map(s => s.status === 'active' ? { ...s, status: 'done' as const } : s)
    );
  }

  const handleResponse = useCallback((response: any) => {
    if (response.hitl_pending) {
      setHitlPending(true);
      setHitlTicker(response.hitl_ticker || '');
      setHitlRawInput(response.hitl_raw_input || '');
      setHitlRunId(response.hitl_run_id || '');
      setMessages(prev => [...prev, {
        id: response.id ?? uuidv4(), role: 'assistant',
        content: response.text, timestamp: new Date(response.timestamp ?? Date.now()),
      }]);
    } else {
      setHitlPending(false);
      setMessages(prev => [...prev, {
        id: response.id ?? uuidv4(), role: 'assistant',
        content: response.text, timestamp: new Date(response.timestamp ?? Date.now()),
        sources: response.sources, isStreaming: false,
      }]);
    }
  }, []);

  const sendStreamingMessage = useCallback(
    async (text: string, attachmentIds?: string[]) => {
      if (!text.trim() && (!attachmentIds || attachmentIds.length === 0)) return;

      // Snapshot IDs now — before any state mutations clear staged files
      const safeIds = (attachmentIds ?? []).filter(Boolean);

      abortStreamRef.current?.();
      abortStreamRef.current = null;
      doneRef.current = false;

      setThoughtSteps([]);
      setTotalElapsed(undefined);
      setIsTraceCollapsed(false);
      streamStartRef.current = Date.now();

      setMessages(prev => [
        ...prev,
        { id: uuidv4(), role: 'user', content: text, timestamp: new Date() },
      ]);

      setIsLoading(true);
      setIsStreaming(true);
      setError(null);
      setHitlPending(false);

      const assistantId = uuidv4();
      setMessages(prev => [
        ...prev,
        { id: assistantId, role: 'assistant', content: '', timestamp: new Date(), isStreaming: true },
      ]);

      const abort = chatService.streamMessage(text, sessionId, safeIds, {
        onThought: (t, et) => pushThoughtStep(t, et),

        onToken: (chunk) => {
          // Drop any tokens that arrive after the stream is complete
          if (doneRef.current) return;
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: m.content + chunk, isStreaming: true }
                : m
            )
          );
        },

        onHitl: ({ run_id, ticker, raw_input, message: hitlMsg }) => {
          doneRef.current = true;
          finaliseThoughtSteps();
          setTotalElapsed((Date.now() - streamStartRef.current) / 1000);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, content: hitlMsg, isStreaming: false } : m
            )
          );
          setHitlPending(true);
          setHitlTicker(ticker);
          setHitlRawInput(raw_input);
          setHitlRunId(run_id);
          setIsLoading(false);
          setIsStreaming(false);
        },

        onDone: (fullText) => {
          doneRef.current = true;
          finaliseThoughtSteps();
          setTotalElapsed((Date.now() - streamStartRef.current) / 1000);
          // Use server's canonical assembled text as source of truth.
          // Falls back to whatever tokens accumulated if fullText is empty.
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: fullText || m.content, isStreaming: false }
                : m
            )
          );
          setIsLoading(false);
          setIsStreaming(false);
          abortStreamRef.current = null;
        },

        onError: (msg) => {
          doneRef.current = true;
          finaliseThoughtSteps();
          setError(msg);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `⚠️ Error: ${msg}. Please try again.`, isStreaming: false }
                : m
            )
          );
          setIsLoading(false);
          setIsStreaming(false);
          abortStreamRef.current = null;
        },
      });

      abortStreamRef.current = abort;
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [sessionId],
  );

  const sendMessage = sendStreamingMessage;

  const confirmTicker = useCallback(
    async (confirmed: boolean, correctedTicker?: string) => {
      if (!hitlRunId) return;
      setIsLoading(true);
      setHitlPending(false);
      try {
        const response = await chatService.confirmTicker({
          session_id: sessionId, run_id: hitlRunId,
          confirmed, corrected_ticker: correctedTicker,
        });
        handleResponse(response);
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Confirmation failed';
        setError(msg);
        setMessages(prev => [...prev, {
          id: uuidv4(), role: 'assistant',
          content: `⚠️ Error: ${msg}. Please try again.`,
          timestamp: new Date(),
        }]);
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, hitlRunId, handleResponse],
  );

  const loadHistory = useCallback(async () => {
    try {
      const history = await chatService.getHistory(sessionId);
      setMessages(history.map(h => ({
        id: h.id, role: h.role as 'user' | 'assistant',
        content: h.content, timestamp: new Date(h.timestamp), sources: h.sources,
      })));
    } catch { /* best-effort */ }
  }, [sessionId]);

  const markStreamingComplete = useCallback((messageId: string) => {
    setMessages(prev => prev.map(m => m.id === messageId ? { ...m, isStreaming: false } : m));
  }, []);

  const clearMessages = useCallback(() => {
    abortStreamRef.current?.();
    abortStreamRef.current = null;
    doneRef.current = false;
    setMessages([]);
    setThoughtSteps([]);
    setTotalElapsed(undefined);
    setHitlPending(false);
    setIsStreaming(false);
    setIsLoading(false);
  }, []);

  return {
    messages, setMessages, isLoading, error,
    isStreaming, sendStreamingMessage, sendMessage,
    thoughtSteps, totalElapsed, isTraceCollapsed, setIsTraceCollapsed,
    hitlPending, hitlTicker, hitlRawInput, confirmTicker,
    loadHistory, markStreamingComplete, clearMessages,
  };
}