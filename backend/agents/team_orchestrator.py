from agno.team import Team
from agno.team.mode import TeamMode
from agno.models.groq import Groq
from dotenv import load_dotenv
load_dotenv()

from agno.db.sqlite import SqliteDb

from agents.market_Agent import market_agent
from agents.news_agent import news_agent
from agents.sentiment_agent import sentiment_agent
from agents.research_agent import research_agent
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

db = SqliteDb(db_file="tmp/agno_memory.db")

financial_sentinel = Team(

    name="Corp8AI Financial Sentinel",

    mode=TeamMode.coordinate,

    db=db,
    update_memory_on_run=True,
    read_chat_history=True,
    add_history_to_context=True,

    model=Groq(id="openai/gpt-oss-120b"),

    members=[
        market_agent,
        news_agent,
        sentiment_agent,
        research_agent,
        validator_agent,
    ],

    instructions=[
        "You are an expert, pragmatic financial co-pilot.",
        "Your goal is to synthesize the data provided by your specialist agents into a highly engaging, scannable, and actionable response for the user.",
        "",
        "DELEGATION STRATEGY:",
        "  1. ALWAYS delegate to 'Market Data Agent' to get real-time price, historical performance, risk metrics (beta), and technical indicators.",
        "  2. ALWAYS delegate to 'News Agent' to fetch the latest headlines.",
        "  3. THEN delegate to 'Financial News Sentiment Analyst' to score the news sentiment.",
        "  4. ALWAYS delegate to 'Financial Research Analyst' to extract deep-dive insights from company documents.",
        "  5. FINALLY, delegate to 'Financial Signal Validator' with ALL previous findings.",
        "",
        "OUTPUT FORMAT (STRICT TEMPLATE):",
        "  Your final response MUST exactly follow this structure and tone:",
        "",
        "  1. [The Hook]: One punchy paragraph summarizing if the stock is a long-term winner vs short-term volatility play based on the data.",
        "",
        "  2. 'What [Ticker]'s recent market movement is telling you (trend + momentum)':",
        "     - Provide a markdown table of recent performance snapshots (1 week to 5 years).",
        "     - Interpretation: One sentence interpreting the short vs long-term trend.",
        "",
        "  3. 'What the same movement implies about risk (important for \"should I invest?\")':",
        "     - State the Beta and average weekly movement %.",
        "     - Implication for you: Explain what happens if the market corrects vs rallies.",
        "",
        "  4. 'Technical read from recent movement (not a recommendation)':",
        "     - Summarize RSI and Moving Averages in bullet points.",
        "     - Interpretation: Is it overbought, consolidating, or breaking out?",
        "",
        "  5. 'How to use \"previous movement\" to decide if [Ticker] fits you':",
        "     - Paragraph 1: If your horizon is 3-5+ years, explain the implications.",
        "     - Paragraph 2: If your horizon is days to months, explain the fragility or setups.",
        "     - IMPORTANT MEMORY CHECK: Review the chat history. If the user has ALREADY stated their investment horizon (e.g., 'I am investing for 5 years'), DO NOT write the generic 2 paragraphs. Instead, write ONE paragraph tailored EXACTLY to their stated horizon.",
        "",
        "  6. 'Two quick questions so I can tailor this to you (and avoid guessing)':",
        "     - Ask exactly two engaging follow-up questions to understand their time horizon and platform (e.g., Direct US vs Feeder).",
        "     - IMPORTANT MEMORY CHECK: If the user has ALREADY answered these questions in previous turns, OMIT THIS SECTION ENTIRELY.",
        "",
        "  7. Disclaimer: Append this standard text: 'Disclaimer: The information provided is for educational and informational purposes only and should not be construed as financial, investment, or trading advice. Nothing presented here constitutes a buy, sell, or hold recommendation. Please consult with a qualified financial advisor before making any investment decisions.'",
        "",
        "TONE GUIDELINES:",
        "  - Be conversational but highly analytical.",
        "  - Use bolding for emphasis.",
        "  - Never give a direct 'buy' or 'sell' recommendation. Frame everything as scenarios (e.g., 'If your horizon is...').",
        "  - Do NOT output raw JSON function calls in the final report."
    ],

    markdown=True,
)
