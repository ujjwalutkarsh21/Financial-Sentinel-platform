// === useSession hook — manages multi-session state with message/file snapshots ===

import { useState, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import type { Message, FileObject, Session } from '../types/chat';

const INITIAL_SESSION_ID = uuidv4();

const INITIAL_SESSION: Session = {
  id: INITIAL_SESSION_ID,
  name: 'New Analysis',
  timestamp: new Date(),
  type: 'data',
};

export function useSession() {
  const [sessions, setSessions] = useState<Session[]>([INITIAL_SESSION]);
  const [activeSessionId, setActiveSessionId] = useState(INITIAL_SESSION_ID);

  // Snapshots: session_id → messages / uploaded files
  const messageSnapshots = useRef<Map<string, Message[]>>(new Map());
  const fileSnapshots = useRef<Map<string, FileObject[]>>(new Map());

  /** Create a new session and switch to it */
  const createSession = useCallback(
    (
      currentMessages: Message[],
      currentFiles: FileObject[],
    ) => {
      // Save current session's state
      messageSnapshots.current.set(activeSessionId, currentMessages);
      fileSnapshots.current.set(activeSessionId, currentFiles);

      const newId = uuidv4();
      const newSession: Session = {
        id: newId,
        name: 'New Analysis',
        timestamp: new Date(),
        type: 'data',
      };
      setSessions(prev => [newSession, ...prev]);
      setActiveSessionId(newId);

      return { newSessionId: newId, messages: [] as Message[], files: [] as FileObject[] };
    },
    [activeSessionId],
  );

  /** Switch to an existing session */
  const switchSession = useCallback(
    (
      targetId: string,
      currentMessages: Message[],
      currentFiles: FileObject[],
    ) => {
      if (targetId === activeSessionId) return null;

      // Save current session's state
      messageSnapshots.current.set(activeSessionId, currentMessages);
      fileSnapshots.current.set(activeSessionId, currentFiles);

      // Load target session's state
      const restoredMessages = messageSnapshots.current.get(targetId) || [];
      const restoredFiles = fileSnapshots.current.get(targetId) || [];

      setActiveSessionId(targetId);

      return { messages: restoredMessages, files: restoredFiles };
    },
    [activeSessionId],
  );

  /** Rename a session (e.g. after first message) */
  const renameSession = useCallback((sessionId: string, name: string) => {
    setSessions(prev =>
      prev.map(s => (s.id === sessionId ? { ...s, name } : s)),
    );
  }, []);

  /** Save a snapshot of messages for the active session (for incremental saves) */
  const saveSnapshot = useCallback(
    (messages: Message[], files: FileObject[]) => {
      messageSnapshots.current.set(activeSessionId, messages);
      fileSnapshots.current.set(activeSessionId, files);
    },
    [activeSessionId],
  );

  return {
    sessions,
    activeSessionId,
    createSession,
    switchSession,
    renameSession,
    saveSnapshot,
  };
}
