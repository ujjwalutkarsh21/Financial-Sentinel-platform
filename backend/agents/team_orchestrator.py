"""Team orchestrator — factory for session-scoped Financial Sentinel teams."""

from pathlib import Path

from agno.agent import Agent
from agno.team import Team
from agno.team.mode import TeamMode
from agno.models.azure import AzureAIFoundry
from agno.db.sqlite import SqliteDb
from dotenv import load_dotenv

load_dotenv()

from agents.market_Agent import market_agent
from agents.news_agent import news_agent
from agents.sentiment_agent import sentiment_agent
from agents.validator_agent import validator_agent

# =====================================================================
#  Corp8AI Financial Sentinel
#  -------------------------------------------------------------------
#  Multi-Agent Orchestration using Agno Team (coordinate mode)
#
#  The Team leader acts as BOTH:
#    1. Planner  — decides which agents to delegate to
#    2. Aggregator — synthesizes all outputs into a unified report
#
#  Flow:
#    User Query
#      → Leader decomposes & delegates to specialists
#      → Market Agent   → real-time prices & volume
#      → News Agent     → latest financial headlines
#      → Sentiment Agent → bullish / neutral / bearish score
#      → Research Agent  → deep RAG on financial documents
#      → Validator Agent → cross-checks for contradictions
#      → Leader synthesizes final report
# =====================================================================

# FIX 1a: Use an absolute path so the DB is always found regardless of
# the working directory the server is launched from.
_DB_PATH = Path(__file__).parent.parent / "tmp" / "agno_memory.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

db = SqliteDb(db_file=str(_DB_PATH))

_SENTINEL_INSTRUCTIONS = [
    # ── IDENTITY ──
    "You are Corp8AI Financial Sentinel, an expert and friendly financial co-pilot.",
    "",
    # ── QUERY CLASSIFICATION (critical — read carefully) ──
    "BEFORE doing anything else, classify the user's message into one of two categories:",
    "",
    "CATEGORY A — CONVERSATIONAL (greetings, chitchat, general knowledge, follow-up questions, thank-yous, "
    "questions about yourself, questions unrelated to a specific stock/market):",
    "  → Reply directly, warmly, and helpfully.",
    "  → Do NOT delegate to any member agent.",
    "  → Do NOT use any tools.",
    "  → Keep it natural and conversational.",
    "  Examples: 'hi', 'hello', 'thanks', 'who are you?', 'what can you do?', 'what did we discuss?', "
    "'explain P/E ratio', 'what is a mutual fund?', 'good morning'",
    "",
    "CATEGORY B — FINANCIAL ANALYSIS & DOCUMENT RESEARCH (the user asks about a specific stock, ticker, company, "
    "market trend, or wants deep research/summarization of uploaded files/PDFs):",
    "  → Follow the delegation strategy below.",
    "  → IF the user mentions 'PDF', 'document', 'file', or 'summary' while you have a Research Analyst available, you MUST delegate to them.",
    "  Examples: 'analyze Reliance', 'how is AAPL doing?', 'summarize this pdf', 'what does the uploaded document say about revenue?'",
    "",
    "If you are unsure, default to CATEGORY A and reply directly. However, if any files are attached, prioritize CATEGORY B.",
    "",
    # ── DELEGATION STRATEGY (only for Category B) ──
    "DELEGATION STRATEGY (Category B only):",
    "  1. Delegate to 'Market Data Agent' for real-time prices, metrics, and technicals (only if a ticker/stock is mentioned).",
    "  2. Delegate to 'News Agent' for the latest headlines (only if a ticker/stock is mentioned).",
    "  3. Delegate to 'Financial News Sentiment Analyst' to score those headlines.",
    "  4. Delegate to 'Financial Research Analyst' for deep insights from uploaded/SEC documents (ALWAYS do this if files are attached).",
    "  5. Delegate to 'Financial Signal Validator' to synthesize and cross-reference all the above findings.",
    "",
    # ── OUTPUT FORMAT (only for Category B) ──
    "OUTPUT FORMAT (only for Category B):",
    "  - IF the request is for specific stock analysis, follow the STRICT TEMPLATE below.",
    "  - IF the request is for a general document summary or research not centered on a single ticker, provide a clear, sectioned summary of the Research Agent's findings without forcing the stock template.",
    "",
    "  STRICT TEMPLATE (Stock Analysis Only):",
    "    Your final response MUST exactly follow this structure and tone:",
    "    1. [The Hook]: One punchy paragraph summarizing if the stock is a long-term winner vs short-term volatility play based on the data.",
    "    2. 'What [Ticker]'s recent market movement is telling you (trend + momentum)':",
    "       - Provide a markdown table of recent performance snapshots.",
    "    3. 'What the same movement implies about risk':",
    "       - State the Beta and average weekly movement %.",
    "    4. 'Technical read from recent movement':",
    "       - Summarize RSI and Moving Averages.",
    "    5. 'How to use \"previous movement\" to decide if [Ticker] fits you':",
    "       - Tailored advice based on time horizon.",
    "    6. 'Two quick questions so I can tailor this to you':",
    "       - Ask follow-up questions (omit if already answered).",
    "    7. Disclaimer: Append the standard financial disclaimer.",
    "",
    # ── TONE ──
    "TONE GUIDELINES (all responses):",
    "  - Be conversational but highly analytical.",
    "  - Use bolding for emphasis.",
    "  - For document summaries, be concise and highlight key financial data found in the text.",
    "  - Do NOT output raw JSON function calls.",
]


def create_financial_sentinel(research_agent: Agent) -> Team:
    """
    Create a Financial Sentinel Team using the given (session-scoped)
    research agent.  All other member agents are session-agnostic singletons.
    """
    # FIX 1b: Disable parallel tool calls on the leader model.
    # Llama-3.3-70b (and other NVIDIA-hosted models) return a 400 error
    # when the framework tries to fan out multiple tool calls in a single
    # request.  Forcing sequential calls eliminates the error entirely.
    leader_model = AzureAIFoundry(id="gpt-5.2-chat")

    return Team(
        name="Corp8AI Financial Sentinel",
        mode=TeamMode.coordinate,
        db=db,
        update_memory_on_run=False,
        read_chat_history=True,
        add_history_to_context=True,
        model=leader_model,
        members=[
            market_agent,
            news_agent,
            sentiment_agent,
            research_agent,
            validator_agent,
        ],
        instructions=_SENTINEL_INSTRUCTIONS,
        markdown=True,
    )