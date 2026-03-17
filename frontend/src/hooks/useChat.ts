// === useChat hook — manages chat state and API calls, scoped by session ===

import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import * as chatService from '../services/chatService';
import type { Message } from '../types/chat';

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /** Send a message and get the AI response */
  const sendMessage = useCallback(async (text: string, attachmentIds?: string[]) => {
    if (!text.trim() && (!attachmentIds || attachmentIds.length === 0)) return;

    // Optimistic: add user message immediately
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

      const aiMessage: Message = {
        id: response.id,
        role: 'assistant',
        content: response.text,
        timestamp: new Date(response.timestamp),
        sources: response.sources,
        isStreaming: true, // triggers typewriter effect
      };

      setMessages(prev => [...prev, aiMessage]);
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : 'Something went wrong';
      setError(errMsg);

      // Add error message as assistant response
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
  }, [sessionId]);

  /** Load chat history from the backend for the current session */
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
      // Silently fail — user starts with empty chat
    }
  }, [sessionId]);

  /** Mark a streaming message as complete */
  const markStreamingComplete = useCallback((messageId: string) => {
    setMessages(prev =>
      prev.map(m => (m.id === messageId ? { ...m, isStreaming: false } : m))
    );
  }, []);

  /** Clear all messages (used when switching sessions) */
  const clearMessages = useCallback(() => {
    setMessages([]);
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
  };
}
