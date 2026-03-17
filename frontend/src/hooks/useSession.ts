// === useSession hook — manages multi-session state with localStorage persistence ===

import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { Message, FileObject, Session } from '../types/chat';

// ── localStorage keys ──────────────────────────────────────────────
const LS_SESSIONS_KEY = 'stockmind_sessions';
const LS_ACTIVE_KEY = 'stockmind_active_session';
const LS_MESSAGES_KEY = 'stockmind_messages';   // JSON: { [sessionId]: Message[] }
const LS_FILES_KEY = 'stockmind_files';         // JSON: { [sessionId]: FileObject[] }

// ── Helpers to safely (de)serialize Dates ─────────────────────────
function parseSessions(raw: string | null): Session[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw) as Array<Session & { timestamp: string }>;
    return arr.map(s => ({ ...s, timestamp: new Date(s.timestamp) }));
  } catch { return []; }
}

function parseMessages(raw: string | null): Record<string, Message[]> {
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw) as Record<string, Array<Message & { timestamp: string }>>;
    const out: Record<string, Message[]> = {};
    for (const [sid, msgs] of Object.entries(obj)) {
      out[sid] = msgs.map(m => ({ ...m, timestamp: new Date(m.timestamp) }));
    }
    return out;
  } catch { return {}; }
}

function parseFiles(raw: string | null): Record<string, FileObject[]> {
  if (!raw) return {};
  try {
    const obj = JSON.parse(raw) as Record<string, Array<FileObject & { uploadedAt: string }>>;
    const out: Record<string, FileObject[]> = {};
    for (const [sid, files] of Object.entries(obj)) {
      // Strip the `file` field — File objects can't be serialized
      out[sid] = files.map(f => ({ ...f, file: undefined, uploadedAt: new Date(f.uploadedAt) }));
    }
    return out;
  } catch { return {}; }
}

// ── Initial state from localStorage ───────────────────────────────
function buildInitialState() {
  const savedSessions = parseSessions(localStorage.getItem(LS_SESSIONS_KEY));
  const savedActiveId = localStorage.getItem(LS_ACTIVE_KEY);

  if (savedSessions.length > 0 && savedActiveId && savedSessions.find(s => s.id === savedActiveId)) {
    return { sessions: savedSessions, activeId: savedActiveId };
  }

  // First visit — create a fresh session
  const id = uuidv4();
  const freshSession: Session = { id, name: 'New Analysis', timestamp: new Date(), type: 'data' };
  return { sessions: [freshSession], activeId: id };
}

export function useSession() {
  const initial = buildInitialState();
  const [sessions, setSessions] = useState<Session[]>(initial.sessions);
  const [activeSessionId, setActiveSessionId] = useState(initial.activeId);

  // Snapshots live in Refs for speed; we also persist them to localStorage
  const messageSnapshots = useRef<Record<string, Message[]>>(parseMessages(localStorage.getItem(LS_MESSAGES_KEY)));
  const fileSnapshots = useRef<Record<string, FileObject[]>>(parseFiles(localStorage.getItem(LS_FILES_KEY)));

  // ── Persist sessions list & active ID whenever they change ──────
  useEffect(() => {
    localStorage.setItem(LS_SESSIONS_KEY, JSON.stringify(sessions));
  }, [sessions]);

  useEffect(() => {
    localStorage.setItem(LS_ACTIVE_KEY, activeSessionId);
  }, [activeSessionId]);

  /** Flush snapshots to localStorage (call after every message/file change) */
  const flushSnapshots = useCallback(() => {
    try {
      localStorage.setItem(LS_MESSAGES_KEY, JSON.stringify(messageSnapshots.current));
      localStorage.setItem(LS_FILES_KEY, JSON.stringify(fileSnapshots.current));
    } catch { /* storage quota — silently ignore */ }
  }, []);

  /** Create a new session and switch to it */
  const createSession = useCallback(
    (currentMessages: Message[], currentFiles: FileObject[]) => {
      messageSnapshots.current[activeSessionId] = currentMessages;
      fileSnapshots.current[activeSessionId] = currentFiles;
      flushSnapshots();

      const newId = uuidv4();
      const newSession: Session = { id: newId, name: 'New Analysis', timestamp: new Date(), type: 'data' };
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newId);

      return { newSessionId: newId, messages: [] as Message[], files: [] as FileObject[] };
    },
    [activeSessionId, flushSnapshots],
  );

  /** Switch to an existing session */
  const switchSession = useCallback(
    (targetId: string, currentMessages: Message[], currentFiles: FileObject[]) => {
      if (targetId === activeSessionId) return null;

      messageSnapshots.current[activeSessionId] = currentMessages;
      fileSnapshots.current[activeSessionId] = currentFiles;
      flushSnapshots();

      const restoredMessages = messageSnapshots.current[targetId] || [];
      const restoredFiles = fileSnapshots.current[targetId] || [];
      setActiveSessionId(targetId);

      return { messages: restoredMessages, files: restoredFiles };
    },
    [activeSessionId, flushSnapshots],
  );

  /** Rename a session */
  const renameSession = useCallback((sessionId: string, name: string) => {
    setSessions(prev => prev.map(s => (s.id === sessionId ? { ...s, name } : s)));
  }, []);

  /** Save a snapshot of messages for the active session */
  const saveSnapshot = useCallback(
    (messages: Message[], files: FileObject[]) => {
      messageSnapshots.current[activeSessionId] = messages;
      fileSnapshots.current[activeSessionId] = files;
      flushSnapshots();
    },
    [activeSessionId, flushSnapshots],
  );

  /** Wipe ALL localStorage keys — called after the backend reset */
  const clearAllPersistence = useCallback(() => {
    localStorage.removeItem(LS_SESSIONS_KEY);
    localStorage.removeItem(LS_ACTIVE_KEY);
    localStorage.removeItem(LS_MESSAGES_KEY);
    localStorage.removeItem(LS_FILES_KEY);
    messageSnapshots.current = {};
    fileSnapshots.current = {};
  }, []);

  return {
    sessions,
    activeSessionId,
    createSession,
    switchSession,
    renameSession,
    saveSnapshot,
    clearAllPersistence,
    /** Return persisted messages/files for a given session (read-only) */
    getSnapshot: (sessionId: string) => ({
      messages: messageSnapshots.current[sessionId] || [] as Message[],
      files: fileSnapshots.current[sessionId] || [] as FileObject[],
    }),
  };
}
