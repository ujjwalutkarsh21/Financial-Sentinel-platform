"""Research agent — factory functions for session-scoped Knowledge + Agent."""

from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.models.azure import AzureOpenAI
from agno.vectordb.lancedb import LanceDb, SearchType
from dotenv import load_dotenv

load_dotenv()


# ── Shared constants ──────────────────────────────────────────────────

_LANCEDB_URI = "tmp/lancedb"
_EMBEDDER = GeminiEmbedder(id="gemini-embedding-001")

# Patch the shared embedder to avoid "empty part" Gemini API errors
# from queries or other search-time components.
def _safe_patch_embedder(emb):
    for m_name in ["get_embedding", "get_embeddings", "embed", "get_embedding_batch"]:
        orig = getattr(emb, m_name, None)
        if orig and callable(orig) and not hasattr(orig, "_is_safe"):
            def _make_safe(o_func):
                def _safe_call(*args, **kwargs):
                    inp = args[0] if args else kwargs.get("text") or kwargs.get("texts")
                    if isinstance(inp, str) and not inp.strip():
                        return [0.0] * getattr(emb, "dimensions", 768)
                    return o_func(*args, **kwargs)
                _safe_call._is_safe = True
                return _safe_call
            setattr(emb, m_name, _make_safe(orig))

_safe_patch_embedder(_EMBEDDER)


_RESEARCH_INSTRUCTIONS = [
    "Use ONLY information from the DOCUMENT CONTEXT.",
    "Do NOT use prior knowledge or invent facts.",
    "If information is not in documents, say 'Not found in the provided documents.'",
    "Cite evidence with direct quotes for every insight.",
    "IF the user asks to 'summarize' or 'explain' a document, provide a comprehensive executive summary highlighting key findings, financial data, and trends mentioned in the text.",
]


# ── Factory functions ─────────────────────────────────────────────────

def create_session_knowledge(session_id: str) -> Knowledge:
    """
    Create a Knowledge instance backed by a **per-session** LanceDB table.

    Table name: ``docs_{session_id}``
    This guarantees complete data isolation between sessions.
    """
    table_name = f"docs_{session_id}"
    vector_db = LanceDb(
        uri=_LANCEDB_URI,
        table_name=table_name,
        search_type=SearchType.vector,
        embedder=_EMBEDDER,
    )
    return Knowledge(vector_db=vector_db)


def create_research_agent(session_id: str) -> Agent:
    """
    Create a research agent whose knowledge is scoped to *session_id*.

    Each call returns a **new** Agent instance so concurrent sessions
    never share mutable state.
    """
    session_kb = create_session_knowledge(session_id)

    return Agent(
        name="Financial Research Analyst",
        role="Deep research on financial documents (SEC filings, earnings reports) using RAG with vector search",
        model=AzureOpenAI(id="gpt-5.2-chat"),
        description="You are a financial research analyst that ONLY uses provided document context.",
        instructions=_RESEARCH_INSTRUCTIONS,
        use_instruction_tags=True,
        expected_output="Concise bullet points with insights and direct citations from documents.",
        additional_context="CRITICAL: Never fabricate data. Every claim must reference a specific document passage.",
        knowledge=session_kb,
        search_knowledge=True,
        add_knowledge_to_context=True,
        markdown=True,
    )