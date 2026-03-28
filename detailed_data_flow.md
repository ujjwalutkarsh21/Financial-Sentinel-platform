# 🌊 Financial Sentinel: Comprehensive Data Flow

This document maps the exact, step-by-step flow of data through the system over time. While the Architecture Diagram shows *what* the system is, these diagrams show *how* it operates chronologically.

---

## 🚦 Flow 1: The Standard Stock Analysis Request (Category B)

This maps the journey of a user asking "How is Apple doing today?".

```mermaid
sequenceDiagram
    autonumber
    
    participant U as User (UI)
    participant H as useChat Hook
    participant Route as routes.py
    participant Svc as analysis_service.py
    participant Orch as Team Orchestrator
    participant Mkt as Market Agent
    participant Tool as market_toolkit
    
    %% The Initiation
    U->>H: Types "How is Apple doing today?"
    H->>H: Generates new assistant message bubble (Loading state)
    H->>Route: fetch("/api/stream?message=...&session_id=...")
    
    %% Handling
    Route->>Svc: stream_orchestrator(message)
    Svc->>Svc: _resolve_ticker("Apple") -> "AAPL"
    
    %% HITL Trigger
    Svc->>Orch: Check _paused_runs for existing session? (No)
    Svc-->>Route: yield SSE [event: hitl, data: {"ticker": "AAPL"}]
    Route-->>H: HTTP Event Stream (hitl)
    H->>U: Pauses stream, shows verification modal: "Confirm AAPL?"
    
    %% The Confirmation
    U->>H: Clicks "Yes, Confirm"
    H->>Route: POST /api/confirm {run_id, confirmed: True}
    Route->>Svc: process_confirm()
    Svc->>Orch: team.run("Complete analysis for AAPL")
    
    %% The Agentic Resolution
    Orch->>Orch: Classifies as Category B
    Orch->>Mkt: Delegates: "Get price data for AAPL"
    Mkt->>Tool: get_stock_data("AAPL")
    Tool-->>Mkt: {"current_price": 225.50, ...}
    Mkt-->>Orch: "AAPL is trading at 225.50..."
    
    %% Streaming the Output Back
    loop Streaming Yields
        Orch-->>Svc: RunResponseDeltaContent ("Apple ")
        Svc-->>Route: yield SSE [event: token, text: "Apple "]
        Route-->>H: Updates React Bubble state
    end
    
    Orch-->>Svc: RunResponseContent (Final assembled report)
    Svc->>Svc: Ignores snapshot to prevent duplication
    Svc-->>Route: yield SSE [event: done]
    Route-->>H: Closes stream, sets isStreaming = false
```

---

## 📄 Flow 2: The Document Upload & RAG Ingestion (Category C)

This maps what happens when a user drops a massive SEC 10-K filing onto the chat window.

```mermaid
sequenceDiagram
    autonumber
    
    participant Drop as Drag&Drop UI
    participant UpSvc as upload_service.py
    participant Svc as analysis_service.py
    participant IngSvc as ingestion_service.py
    participant Gem as Gemini API
    participant DB as LanceDB
    
    %% Storing the File
    Drop->>UpSvc: POST /api/upload (Multipart form data: Q1_Report.pdf)
    UpSvc->>UpSvc: mkdir /tmp/uploads/UUID/
    UpSvc->>UpSvc: Saves physical file to disk
    UpSvc-->>Drop: Returns file_id="abc-123"
    
    Note over Drop, DB: File is queued. Ingestion happens on the NEXT message.
    
    %% The Ingestion Trigger
    Drop->>Svc: POST /api/stream (message="...", attachments="abc-123")
    Svc->>IngSvc: ingest_files_for_session([abc-123])
    
    %% The Vector Processing (with guards)
    IngSvc->>IngSvc: Parses PDF into 50 pages of text.
    IngSvc->>IngSvc: Page 2 is a blank cover page ("")
    
    IngSvc->>DB: knowledge.insert(reader)
    DB->>IngSvc: intercepts via "Gemini Guard" Monkeypatch
    IngSvc->>IngSvc: Drops Page 2 string to prevent crash
    
    IngSvc->>Gem: get_embeddings([Page 1 text, Page 3 text...])
    Gem-->>IngSvc: Returns [ [0.5, 0.2...], [0.1, 0.8...] ]
    IngSvc->>DB: stores vectors in table "docs_UUID"
    
    %% Context Building
    Svc->>Svc: Appends hidden system prompt to user message:
    Note right of Svc: "[SYSTEM: User uploaded Q1_Report.pdf. Delegate to Research Analyst.]"
    
    Svc->>Orch: Runs team with enriched message
    Note right of Orch: Process follows the standard Agentic Flow but restricts search ONLY to "docs_UUID" table.
```

---

## 🛠️ Tracing the Data Shapes

To truly understand the flow, you must understand the shape of the data at each boundary.

### 1. The React [Message](file:///d:/internship/Projects/stock_market_analysis/frontend/src/services/chatService.ts#144-147) Type (Frontend)
```typescript
{
  id: "uuid-4",
  role: "user" | "assistant",
  content: "Actual text rendered on screen",
  isStreaming: true,
  sources: [...] // If citations exist
}
```

### 2. The HTTP API Request Body
```json
{
  "message": "Analyze Apple",
  "session_id": "user_session_99",
  "attachments": ["file_id_1"]
}
```

### 3. The Enriched Prompt (Backend Internal)
```text
[SYSTEM: The user has uploaded 1 document(s) indexed in the knowledge base: 'Q1_Report.pdf'. This is a DOCUMENT RESEARCH query (Category C or B+C). Delegate to 'Financial Research Analyst' immediately. The documents ARE available — do NOT say they are missing.]

Analyze Apple.
```

### 4. The Agno Raw `TeamMemberAgentStarted` Event
```python
RunEvent(
    event="TeamMemberAgentStarted",
    agent="market_Agent",
    team="Financial Sentinel",
    content=None
)
```

### 5. The Transformed SSE Event Stream (Sent to Browser)
```http
event: thought
data: {"text": "market_Agent", "event_type": "AgentRunStarted"}

event: token
data: {"text": "Apple"}

event: token
data: {"text": " is trading at "}
```

### 6. The SQLite Persistence Schema ([history_service.py](file:///d:/internship/Projects/stock_market_analysis/backend/services/history_service.py))
```json
{
  "session_id": "user_session_99",
  "messages": [
    {"role": "user", "content": "Analyze Apple", "timestamp": "2024-01-01T..."}
  ]
}
```
