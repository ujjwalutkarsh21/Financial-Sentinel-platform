/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect, useRef } from 'react';
import { useChat } from './hooks/useChat';
import { useUpload } from './hooks/useUpload';
import { useSession } from './hooks/useSession';
import { 
  Send, 
  Paperclip, 
  X, 
  FileText, 
  Table, 
  File as FileIcon, 
  LogOut, 
  Plus, 
  TrendingUp, 
  AlertCircle,
  Cpu,
  Database,
  Globe
} from 'lucide-react';
import { resetSession as apiResetSession } from './services/chatService';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { v4 as uuidv4 } from 'uuid';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// === UTILS ===
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// === TYPES ===
interface FileObject {
  id: string;
  name: string;
  size: number;
  type: string;
  uploadedAt: Date;
  file?: File;
  /** ID returned from backend after upload */
  remoteId?: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  files?: FileObject[];
  data?: any;
  sources?: string[];
  isStreaming?: boolean;
  hitl?: {
    type: 'ticker_confirmation';
    ticker: string;
  };
}

interface Session {
  id: string;
  name: string;
  timestamp: Date;
  type: 'research' | 'data' | 'upload';
}

// === COMPONENTS ===

const Typewriter = ({ text, onComplete }: { text: string, onComplete?: () => void }) => {
  const [displayedText, setDisplayedText] = useState('');
  const [index, setIndex] = useState(0);

  useEffect(() => {
    if (index < text.length) {
      const timeout = setTimeout(() => {
        setDisplayedText(prev => prev + text[index]);
        setIndex(prev => prev + 1);
      }, 5);
      return () => clearTimeout(timeout);
    } else if (onComplete) {
      onComplete();
    }
  }, [index, text, onComplete]);

  return (
    <div className="relative markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayedText}</ReactMarkdown>
      {index < text.length && (
        <span className="inline-block w-1.5 h-4 bg-[#00FF85] ml-1 animate-pulse align-middle" />
      )}
    </div>
  );
};

const MetricCard = ({ label, value, trend, highlight }: { label: string, value: string, trend: string, highlight?: boolean }) => (
  <div className={cn(
    "p-3 border border-white/10 bg-[#121418] flex flex-col gap-1",
    highlight && "border-[#00FF85]/30 bg-[#00FF85]/5"
  )}>
    <span className="text-[10px] font-mono uppercase text-white/40 tracking-wider">{label}</span>
    <div className="flex items-center justify-between">
      <span className={cn(
        "text-lg font-mono font-bold",
        highlight ? "text-[#00FF85]" : "text-[#E8EDF2]"
      )}>{value}</span>
      {trend === 'up' && <TrendingUp size={14} className="text-[#00FF85]" />}
    </div>
  </div>
);

const DataTable = ({ headers, rows }: { headers: string[], rows: string[][] }) => (
  <div className="w-full overflow-x-auto border border-white/10 mt-4">
    <table className="w-full text-left font-mono text-xs">
      <thead>
        <tr className="bg-white/5 border-b border-white/10">
          {headers.map((h, i) => (
            <th key={i} className="p-2 uppercase text-white/40 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-white/5 last:border-0 hover:bg-white/5 transition-colors">
            {row.map((cell, j) => (
              <td key={j} className="p-2 text-[#E8EDF2]">{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default function StockMindChat() {
  // === SESSION HOOK ===
  const session = useSession();

  // === HOOKS (scoped by session) ===
  const chat = useChat(session.activeSessionId);
  const uploadHook = useUpload(session.activeSessionId);

  // === STATE ===
  const messages = chat.messages;
  const setMessages = chat.setMessages;
  const [inputText, setInputText] = useState('');
  const attachedFiles = uploadHook.stagedFiles;
  const [uploadedFiles, setUploadedFiles] = useState<FileObject[]>([]);
  const isStreaming = chat.isLoading;
  const [isDragging, setIsDragging] = useState(false);
  const [exitModalOpen, setExitModalOpen] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const [agentStatus, setAgentStatus] = useState({
    data: false,
    research: false,
    rag: false
  });
  // Track whether the first message of a session has been sent (for auto-rename)
  const firstMessageSentRef = useRef<Set<string>>(new Set());

  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // === EFFECTS ===

  // Restore persisted messages for the active session on mount / session switch
  useEffect(() => {
    const snapshot = session.getSnapshot(session.activeSessionId);
    if (snapshot.messages.length > 0 && messages.length === 0) {
      setMessages(snapshot.messages);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.activeSessionId]);

  // Save snapshot whenever messages change so localStorage stays in sync
  useEffect(() => {
    if (messages.length > 0) {
      session.saveSnapshot(messages, uploadedFiles);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // === HANDLERS ===
  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!inputText.trim() && attachedFiles.length === 0) return;

    const text = inputText;
    const fileIds = uploadHook.getStagedIds();
    setInputText('');

    // Move attached to uploaded sidebar
    if (attachedFiles.length > 0) {
      setUploadedFiles(prev => [...prev, ...attachedFiles]);
      uploadHook.clearStaged();
    }

    // Auto-rename session after first user message
    if (!firstMessageSentRef.current.has(session.activeSessionId)) {
      firstMessageSentRef.current.add(session.activeSessionId);
      const truncated = text.length > 28 ? text.substring(0, 28) + '…' : text;
      session.renameSession(session.activeSessionId, truncated);
    }

    // Show agent activity
    setAgentStatus({ data: true, research: true, rag: fileIds.length > 0 });

    // This calls the API with optimistic user message insertion
    await chat.sendMessage(text, fileIds.length > 0 ? fileIds : undefined);

    setAgentStatus({ data: false, research: false, rag: false });
  };

  const handleNewChat = () => {
    session.createSession(messages, uploadedFiles);
    chat.clearMessages();
    setUploadedFiles([]);
  };

  const handleExit = async () => {
    setIsExiting(true);
    try {
      await apiResetSession();
    } catch { /* best-effort */ }
    session.clearAllPersistence();
    // Hard reload gives a completely fresh state
    window.location.reload();
  };

  const handleSwitchSession = (targetId: string) => {
    const result = session.switchSession(targetId, messages, uploadedFiles);
    if (result) {
      setMessages(result.messages);
      setUploadedFiles(result.files);
    }
  };

  const handleFileAttach = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    // Upload each file immediately via the hook
    files.forEach(f => uploadHook.upload(f));
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const removeAttachedFile = (id: string) => {
    uploadHook.removeFile(id);
  };

  const removeUploadedFile = (id: string) => {
    setUploadedFiles(prev => prev.filter(f => f.id !== id));
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach(f => uploadHook.upload(f));
  };

  const handleTickerConfirm = async () => {
    await chat.confirmTicker(true);
    setAgentStatus({ data: true, research: true, rag: false });
    // Status will clear when response arrives
  };

  const handleTickerReject = async (newTicker: string) => {
    if (!newTicker.trim()) return;
    await chat.confirmTicker(false, newTicker.trim().toUpperCase());
    setAgentStatus({ data: true, research: true, rag: false });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
  };

  return (
    <div className="flex h-screen w-full bg-[#0A0C10] text-[#E8EDF2] overflow-hidden font-['Syne']">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;500;600;700;800&display=swap');
        
        body {
          background-color: #0A0C10;
          background-image: radial-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px);
          background-size: 24px 24px;
        }

        .font-mono {
          font-family: 'Space Mono', monospace;
        }

        ::-webkit-scrollbar {
          width: 4px;
        }
        ::-webkit-scrollbar-track {
          background: transparent;
        }
        ::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
        }
        ::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.2);
        }

        .scanline {
          width: 100%;
          height: 100px;
          z-index: 10;
          background: linear-gradient(0deg, rgba(0, 0, 0, 0) 0%, rgba(255, 255, 255, 0.02) 50%, rgba(0, 0, 0, 0) 100%);
          opacity: 0.1;
          position: absolute;
          bottom: 100%;
          animation: scanline 10s linear infinite;
        }

        @keyframes scanline {
          0% { bottom: 100%; }
          100% { bottom: -100px; }
        }

        .agent-pulse {
          box-shadow: 0 0 8px rgba(0, 255, 133, 0.4);
          animation: pulse 2s infinite;
        }

        @keyframes pulse {
          0% { opacity: 0.6; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.1); }
          100% { opacity: 0.6; transform: scale(1); }
        }
      `}</style>

      {/* LEFT SIDEBAR */}
      <aside className="hidden lg:flex flex-col w-[280px] border-r border-white/5 bg-[#080A0D] z-20">
        <div className="p-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-[#00FF85] flex items-center justify-center rounded-sm">
            <TrendingUp size={20} className="text-[#0A0C10]" />
          </div>
          <h1 className="text-xl font-extrabold tracking-tighter text-[#00FF85]">STOCKMIND</h1>
        </div>

        <div className="flex-1 overflow-y-auto px-4 space-y-8">
          {/* SESSIONS */}
          <div>
            <h3 className="text-[10px] uppercase tracking-[0.2em] text-white/30 font-bold mb-4 px-2">Active Sessions</h3>
            <div className="space-y-1">
              {session.sessions.map((s, idx) => (
                <motion.button
                  key={s.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  onClick={() => handleSwitchSession(s.id)}
                  className={cn(
                    "w-full group relative flex flex-col items-start p-3 transition-all hover:bg-white/5 border-l-2",
                    session.activeSessionId === s.id ? "border-[#00FF85] bg-white/5" : "border-transparent"
                  )}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <div className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      s.type === 'research' ? "bg-blue-400" : s.type === 'data' ? "bg-[#00FF85]" : "bg-amber-400"
                    )} />
                    <span className="text-sm font-medium truncate w-40 text-left">{s.name}</span>
                  </div>
                  <span className="text-[10px] font-mono text-white/20">{s.timestamp.toLocaleDateString()}</span>
                </motion.button>
              ))}
            </div>
          </div>

          {/* UPLOADED FILES */}
          <div>
            <h3 className="text-[10px] uppercase tracking-[0.2em] text-white/30 font-bold mb-4 px-2">Uploaded Files</h3>
            <div className="space-y-2">
              <AnimatePresence>
                {uploadedFiles.map((file) => (
                  <motion.div
                    key={file.id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="p-3 bg-white/5 border border-white/5 flex items-center gap-3 group"
                  >
                    <div className="text-white/40">
                      {file.type.includes('pdf') ? <FileText size={18} /> : <Table size={18} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{file.name}</p>
                      <p className="text-[10px] font-mono text-white/20">{formatSize(file.size)}</p>
                    </div>
                    <button 
                      onClick={() => removeUploadedFile(file.id)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-400 transition-all"
                    >
                      <X size={14} />
                    </button>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-white/5">
          <button
            onClick={handleNewChat}
            className="w-full py-3 bg-white/5 hover:bg-white/10 border border-white/10 flex items-center justify-center gap-2 transition-all active:scale-95"
          >
            <Plus size={18} />
            <span className="text-sm font-bold uppercase tracking-wider">New Chat</span>
          </button>
        </div>
      </aside>

      {/* MAIN PANEL */}
      <main className="flex-1 flex flex-col relative">
        <div className="scanline" />
        
        {/* TOP BAR */}
        <header className="h-12 border-b border-white/5 flex items-center justify-between px-6 bg-[#0A0C10]/80 backdrop-blur-md z-30">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-bold cursor-pointer hover:text-[#00FF85] transition-colors">
              {session.sessions.find(s => s.id === session.activeSessionId)?.name || 'Untitled Session'}
            </h2>
            <div className="h-4 w-[1px] bg-white/10" />
            <div className="flex items-center gap-2">
              <div className={cn(
                "flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-tighter border transition-all",
                agentStatus.data ? "border-[#00FF85]/50 text-[#00FF85] bg-[#00FF85]/5 agent-pulse" : "border-white/10 text-white/30"
              )}>
                <Database size={10} />
                Data Agent
              </div>
              <div className={cn(
                "flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-tighter border transition-all",
                agentStatus.research ? "border-[#00FF85]/50 text-[#00FF85] bg-[#00FF85]/5 agent-pulse" : "border-white/10 text-white/30"
              )}>
                <Globe size={10} />
                News Agent
              </div>
              <div className={cn(
                "flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-tighter border transition-all",
                agentStatus.rag ? "border-[#00FF85]/50 text-[#00FF85] bg-[#00FF85]/5 agent-pulse" : "border-white/10 text-white/30"
              )}>
                <Cpu size={10} />
                RAG Agent
              </div>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setExitModalOpen(true)}
              title="Exit — clears all chats, uploads and memory"
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold uppercase tracking-wider text-red-400 border border-red-400/30 hover:bg-red-400/10 hover:border-red-400/60 transition-all active:scale-95"
            >
              <LogOut size={14} />
              Exit
            </button>
          </div>

          {/* EXIT CONFIRMATION MODAL */}
          <AnimatePresence>
            {exitModalOpen && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
                onClick={() => !isExiting && setExitModalOpen(false)}
              >
                <motion.div
                  initial={{ scale: 0.9, opacity: 0, y: 20 }}
                  animate={{ scale: 1, opacity: 1, y: 0 }}
                  exit={{ scale: 0.9, opacity: 0, y: 20 }}
                  transition={{ type: 'spring', damping: 20 }}
                  onClick={e => e.stopPropagation()}
                  className="bg-[#0E1014] border border-red-400/30 p-8 max-w-sm w-full mx-4"
                >
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-red-400/10 border border-red-400/30 flex items-center justify-center">
                      <LogOut size={20} className="text-red-400" />
                    </div>
                    <div>
                      <h2 className="text-base font-extrabold tracking-tight">Exit Session?</h2>
                      <p className="text-[11px] text-white/30 font-mono">This cannot be undone</p>
                    </div>
                  </div>
                  <p className="text-sm text-white/60 mb-6 leading-relaxed">
                    This will permanently delete <span className="text-white font-bold">all chats</span>,
                    <span className="text-white font-bold"> uploaded files</span>, and
                    <span className="text-white font-bold"> AI memory</span> for every session.
                    The page will refresh to a clean state.
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setExitModalOpen(false)}
                      disabled={isExiting}
                      className="flex-1 py-2.5 text-xs font-bold uppercase tracking-wider border border-white/10 hover:bg-white/5 transition-all disabled:opacity-40"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleExit}
                      disabled={isExiting}
                      className="flex-1 py-2.5 text-xs font-bold uppercase tracking-wider bg-red-500 hover:bg-red-600 text-white transition-all active:scale-95 disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {isExiting ? 'Clearing…' : 'Exit & Clear All'}
                    </button>
                  </div>
                </motion.div>
              </motion.div>
            )}
          </AnimatePresence>
        </header>

        {/* CHAT AREA */}
        <div 
          className="flex-1 overflow-y-auto p-6 space-y-8 relative"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* DRAG OVERLAY */}
          <AnimatePresence>
            {isDragging && (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 z-50 bg-[#0A0C10]/80 backdrop-blur-sm flex items-center justify-center p-12"
              >
                <div className="w-full h-full border-2 border-dashed border-[#00FF85] flex flex-col items-center justify-center gap-4 bg-[#00FF85]/5">
                  <div className="w-16 h-16 rounded-full bg-[#00FF85]/10 flex items-center justify-center">
                    <Plus size={32} className="text-[#00FF85]" />
                  </div>
                  <p className="text-xl font-bold uppercase tracking-widest text-[#00FF85]">Drop files to research</p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {messages.map((msg, idx) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 20, x: msg.role === 'user' ? 20 : -20 }}
              animate={{ opacity: 1, y: 0, x: 0 }}
              transition={{ delay: 0.1 }}
              className={cn(
                "flex flex-col max-w-[85%] lg:max-w-[70%]",
                msg.role === 'user' ? "ml-auto items-end" : "mr-auto items-start"
              )}
            >
              <div className={cn(
                "p-4 relative",
                msg.role === 'user' 
                  ? "bg-[#121418] border-l-2 border-[#00FF85]" 
                  : "bg-[#0E1014] border border-white/5"
              )}>
                <div className="text-sm leading-relaxed markdown-body">
                  {msg.isStreaming ? (
                    <Typewriter text={msg.content} onComplete={() => {
                      setMessages(prev => prev.map(m => m.id === msg.id ? { ...m, isStreaming: false } : m));
                    }} />
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  )}
                </div>

                {/* DATA CARDS */}
                {msg.data?.metrics && (
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-4">
                    {msg.data.metrics.map((m: any, i: number) => (
                      <MetricCard key={i} {...m} />
                    ))}
                  </div>
                )}

                {/* DATA TABLE */}
                {msg.data?.table && (
                  <DataTable {...msg.data.table} />
                )}

                {/* SOURCES */}
                {msg.sources && msg.sources.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-4 pt-4 border-t border-white/5">
                    {msg.sources.map((source, i) => (
                      <div key={i} className="flex items-center gap-1.5 px-2 py-1 bg-white/5 text-[10px] font-mono text-white/40 border border-white/5">
                        {source.includes('.pdf') ? <FileText size={10} /> : <Globe size={10} />}
                        {source}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              <span className="text-[9px] font-mono text-white/20 mt-2">
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </motion.div>
          ))}
          <div ref={chatEndRef} />
        </div>

        {/* INPUT AREA */}
        <div className="p-6 bg-gradient-to-t from-[#0A0C10] via-[#0A0C10] to-transparent">
          <div className="max-w-4xl mx-auto relative">

            {/* HITL CONFIRMATION BANNER */}
            <AnimatePresence>
              {chat.hitlPending && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  className="mb-4 border border-amber-500/30 bg-amber-500/5 p-5"
                >
                  <div className="flex items-center gap-2 mb-3 text-amber-500">
                    <AlertCircle size={18} />
                    <span className="text-xs font-bold uppercase tracking-wider">Ticker Confirmation Required</span>
                  </div>
                  <p className="text-sm mb-4 text-white/70">
                    I resolved <span className="font-mono font-bold text-white">"{chat.hitlRawInput}"</span> → <span className="font-mono font-bold text-amber-400 text-lg">{chat.hitlTicker}</span>
                  </p>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleTickerConfirm}
                      disabled={isStreaming}
                      className="px-5 py-2.5 bg-[#00FF85] text-black text-xs font-bold uppercase tracking-wider hover:bg-[#00FF85]/80 transition-all active:scale-95 disabled:opacity-50"
                    >
                      ✓ Confirm {chat.hitlTicker}
                    </button>
                    <div className="flex items-center gap-2">
                      <input
                        id="hitl-correction-input"
                        type="text"
                        placeholder="Enter correct ticker"
                        className="bg-[#121418] border border-white/10 px-3 py-2 text-xs font-mono uppercase w-36 focus:border-amber-500/50 focus:outline-none"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            const el = e.target as HTMLInputElement;
                            handleTickerReject(el.value);
                          }
                        }}
                      />
                      <button
                        onClick={() => {
                          const el = document.getElementById('hitl-correction-input') as HTMLInputElement;
                          if (el?.value) handleTickerReject(el.value);
                        }}
                        disabled={isStreaming}
                        className="px-4 py-2.5 border border-amber-500/30 text-amber-500 text-xs font-bold uppercase tracking-wider hover:bg-amber-500/10 transition-all active:scale-95 disabled:opacity-50"
                      >
                        Change
                      </button>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
            <div className="bg-[#121418] border border-white/10 p-2 focus-within:border-[#00FF85]/50 transition-all">
              
              {/* FILE PREVIEW CHIPS */}
              <AnimatePresence>
                {attachedFiles.length > 0 && (
                  <div className="flex flex-wrap gap-2 p-2 mb-2 border-b border-white/5">
                    {attachedFiles.map((file) => (
                      <motion.div
                        key={file.id}
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        className="flex items-center gap-2 px-2 py-1 bg-[#00FF85]/10 border border-[#00FF85]/20 text-[#00FF85]"
                      >
                        <FileIcon size={12} />
                        <span className="text-[10px] font-mono font-bold truncate max-w-[100px]">{file.name}</span>
                        <button onClick={() => removeAttachedFile(file.id)} className="hover:text-white">
                          <X size={12} />
                        </button>
                      </motion.div>
                    ))}
                  </div>
                )}
              </AnimatePresence>

              <div className="flex items-end gap-2">
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  className="p-3 text-white/40 hover:text-[#00FF85] transition-colors"
                >
                  <Paperclip size={20} />
                </button>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  onChange={handleFileAttach} 
                  multiple 
                  className="hidden" 
                  accept=".pdf,.csv,.xlsx,.txt,.docx"
                />
                <textarea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  placeholder="Ask about a stock, market trend, or upload a report..."
                  className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-3 font-mono resize-none min-h-[44px] max-h-[200px]"
                  rows={1}
                />
                <button 
                  onClick={() => handleSendMessage()}
                  disabled={!inputText.trim() && attachedFiles.length === 0}
                  className={cn(
                    "p-3 transition-all active:scale-90",
                    (inputText.trim() || attachedFiles.length > 0) ? "text-[#00FF85]" : "text-white/10"
                  )}
                >
                  <Send size={20} />
                </button>
              </div>
            </div>
            <p className="text-[10px] text-white/20 mt-3 text-center uppercase tracking-widest">
              Attach PDFs, CSVs, or reports for company-specific RAG analysis
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}
