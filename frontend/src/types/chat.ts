// === Chat domain types (used by components and hooks) ===

export interface FileObject {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: Date;
  file?: File;
  /** ID returned from the backend after upload */
  remoteId?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  files?: FileObject[];
  data?: Record<string, unknown>;
  sources?: string[];
  isStreaming?: boolean;
  isLoading?: boolean;
  hitl?: {
    type: 'ticker_confirmation';
    ticker: string;
  };
}

export interface Session {
  id: string;
  name: string;
  timestamp: Date;
  type: 'research' | 'data' | 'upload';
}
