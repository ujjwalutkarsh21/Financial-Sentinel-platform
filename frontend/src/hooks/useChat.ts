// === useChat hook — manages chat state and API calls, scoped by session ===

import { useState, useCallback } from 'react';
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

  /** Handle a ChatResponse — either final or HITL-pending */
  const handleResponse = useCallback((response: any) => {
    if (response.hitl_pending) {
      setHitlPending(true);
      setHitlTicker(response.hitl_ticker || '');
      setHitlRawInput(response.hitl_raw_input || '');
      setHitlRunId(response.hitl_run_id || '');

      // Add an informational message
      const infoMessage: Message = {
        id: response.id,
        role: 'assistant',
        content: response.text,
        timestamp: new Date(response.timestamp),
      };
      setMessages(prev => [...prev, infoMessage]);
    } else {
      setHitlPending(false);
      const aiMessage: Message = {
        id: response.id,
        role: 'assistant',
        content: response.text,
        timestamp: new Date(response.timestamp),
        sources: response.sources,
        isStreaming: true,
      };
      setMessages(prev => [...prev, aiMessage]);
    }
  }, []);

  /** Send a message and get the AI response */
  const sendMessage = useCallback(async (text: string, attachmentIds?: string[]) => {
    if (!text.trim() && (!attachmentIds || attachmentIds.length === 0)) return;

    const userMessage: Message = {
      id: uuidv4(),
      role: 'user',
      content: text,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const response = await chatService.sendMessage({
        message: text,
        session_id: sessionId,
        attachments: attachmentIds,
      });
      handleResponse(response);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Something went wrong';
      setError(errMsg);
      const errorMessage: Message = {
        id: uuidv4(),
        role: 'assistant',
        content: `⚠️ Error: ${errMsg}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, handleResponse]);

  /** Confirm or reject a ticker during HITL */
  const confirmTicker = useCallback(async (confirmed: boolean, correctedTicker?: string) => {
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
      const errorMessage: Message = {
        id: uuidv4(),
        role: 'assistant',
        content: `⚠️ Error: ${errMsg}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, hitlRunId, handleResponse]);

  /** Load chat history from the backend */
  const loadHistory = useCallback(async () => {
    try {
      const history = await chatService.getHistory(sessionId);
      const mapped: Message[] = history.map(h => ({
        id: h.id,
        role: h.role,
        content: h.content,
        timestamp: new Date(h.timestamp),
        sources: h.sources,
      }));
      setMessages(mapped);
    } catch {
      // Silently fail
    }
  }, [sessionId]);

  /** Mark a streaming message as complete */
  const markStreamingComplete = useCallback((messageId: string) => {
    setMessages(prev =>
      prev.map(m => (m.id === messageId ? { ...m, isStreaming: false } : m))
    );
  }, []);

  /** Clear all messages */
  const clearMessages = useCallback(() => {
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
