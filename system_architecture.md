# 🗺️ Financial Sentinel: Full System Architecture

This document provides a highly detailed, end-to-end visual map of the entire codebase. Use this diagram to trace the execution flow of a prompt from the user's browser all the way down to the LanceDB vector store and the Agno Agent LLM calls.

## The End-to-End Workflow Diagram

```mermaid
flowchart TD
    %% Styling
    classDef frontend fill:#3b82f6,stroke:#1d4ed8,color:white
    classDef backend fill:#10b981,stroke:#047857,color:white
    classDef agent fill:#8b5cf6,stroke:#6d28d9,color:white
    classDef storage fill:#f59e0b,stroke:#b45309,color:white
    classDef external fill:#ef4444,stroke:#b91c1c,color:white

    %% ----------------------------------------------------
    %% FRONTEND ECOSYSTEM (React + Vite)
    %% ----------------------------------------------------
    subgraph Frontend["💻 Frontend (React / Vite)"]
        direction TB
        App["App.tsx\n(Main Layout)"]
        ChatUI["Chat Window\n(Renders Messages)"]
        TraceUI["ThoughtTrace.tsx\n(Renders LLM internal thoughts)"]
        
        HookChat["useChat.ts\n(Manages SSE Streams & AbortControllers)"]
        HookUpload["useUpload.ts\n(Drag & Drop Logic)"]
        HookSession["useSession.ts\n(Local Storage Sync)"]
        
        SvcChat["chatService.ts\n(Raw Fetch Wrappers)"]
        
        App --> ChatUI
        App --> TraceUI
        ChatUI --> HookChat
        TraceUI -. "Listens to 'thought' events" .-> HookChat
        App --> HookUpload
        App --> HookSession
        HookChat --> SvcChat
    end

    %% ----------------------------------------------------
    %% BACKEND API & SERVICES (FastAPI)
    %% ----------------------------------------------------
    subgraph Backend["⚙️ Backend (FastAPI Python)"]
        direction TB
        Routes["api/routes.py\n(FastAPI Endpoints)"]
        
        SvcUpload["services/upload_service.py\n(Saves physical PDFs)"]
        SvcIngest["services/ingestion_service.py\n(Chunking & 'Gemini Guard' patching)"]
        SvcAnalysis["services/analysis_service.py\n(SSE Filtering & HITL Orchestrator)"]
        SvcHistory["services/history_service.py\n(Persistent flat-file logger)"]
        
        Routes -- "POST /upload" --> SvcUpload
        Routes -- "GET /stream" --> SvcAnalysis
        Routes -- "POST /confirm" --> SvcAnalysis
        Routes -- "GET /history" --> SvcHistory
        
        SvcAnalysis -- "If attachments exist" --> SvcIngest
    end

    %% ----------------------------------------------------
    %% AGENTIC BRAIN (Agno Framework)
    %% ----------------------------------------------------
    subgraph Agents["🧠 Agentic Framework (Agno)"]
        direction TB
        Orchestrator["agents/team_orchestrator.py\n(Determines Category A, B, C)"]
        
        MktAgent["agents/market_Agent.py\n(Numbers Specialist)"]
        NewsAgent["agents/news_agent.py\n(Narrative Specialist)"]
        SentAgent["agents/sentiment_agent.py\n(Scores Bullish/Bearish)"]
        ResAgent["agents/research_agent.py\n(RAG Specialist)"]
        ValAgent["agents/validator_agent.py\n(Checks for contradictions)"]
        
        Tools["tools/market_tool.py\n(yfinance fetchers)"]
        
        SvcAnalysis -- "team.run()" --> Orchestrator
        Orchestrator --> MktAgent
        Orchestrator --> NewsAgent
        Orchestrator --> SentAgent
        Orchestrator --> ResAgent
        Orchestrator --> ValAgent
        
        MktAgent --> Tools
    end

    %% ----------------------------------------------------
    %% STORAGE & DATABASES
    %% ----------------------------------------------------
    subgraph Storage["💾 Storage (Local Disk)"]
        direction TB
        tmpUploads[("tmp/uploads/\n(Raw PDF Files)")]
        LanceDB[("tmp/lancedb/\n(Vector DB - Per session tables)")]
        SQLite[("tmp/agno_memory.db\n(Agent Chat History)")]
        
        SvcUpload --> tmpUploads
        SvcIngest --> LanceDB
        ResAgent -- "Similarity Search" --> LanceDB
        Orchestrator --> SQLite
    end

    %% ----------------------------------------------------
    %% EXTERNAL APIS
    %% ----------------------------------------------------
    subgraph External["🌍 External APIs"]
        direction TB
        OpenAI["Azure OpenAI Global\n(gpt-5.2-chat / LLM Reasoning)"]
        Gemini["Google Gemini\n(Embeddings)"]
        YFinance["Yahoo Finance\n(Live Stock Data)"]
        DDG["DuckDuckGo\n(Web Scraping for News)"]
        
        Orchestrator --> OpenAI
        MktAgent --> OpenAI
        ResAgent --> OpenAI
        
        SvcIngest --> Gemini
        Tools --> YFinance
        NewsAgent --> DDG
    end

    %% ----------------------------------------------------
    %% CROSS-LAYER CONNECTIONS
    %% ----------------------------------------------------
    SvcChat -- "HTTP SSE Stream" --> Routes
    
    class Frontend frontend
    class Backend backend
    class Agents agent
    class Storage storage
    class External external
```

### 🔍 How to Read This Diagram
1. **The User Input (`SvcChat -> Routes`)**: A user types a message. The request flows from the React hooks over an SSE connection to the FastAPI [routes.py](file:///d:/internship/Projects/stock_market_analysis/backend/api/routes.py).
2. **The Orchestrator (`SvcAnalysis`)**: The heartbeat of the app. It checks for PDFs (routing to `SvcIngest`), enriches the prompt, and hands control to the `Team`.
3. **The Multi-Agent Web (`Agents`)**: The `Team Lead` uses its strict instructions to classify the prompt and delegate out to its specialist members.
4. **Data Sourcing (`External`)**: The agents use tools to break out to the real world — querying Yahoo Finance, DuckDuckGo, and pulling from the local `LanceDB` vector store.
