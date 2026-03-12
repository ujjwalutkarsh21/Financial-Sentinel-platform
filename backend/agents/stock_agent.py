from agno.agent import Agent
from tools.market_tool import get_stock_data
from tools.news_tool import search_news
from agno.models.groq import Groq
from dotenv import load_dotenv
from agno.tools.duckduckgo import DuckDuckGoTools

load_dotenv()

stock_agent = Agent(
    model=Groq(id="openai/gpt-oss-120b"),
    name="Stock Movement Analyst",

    instructions="""
        You are a financial analysis assistant.

        Rules you must follow:

        1. Always use the available tools to retrieve market data and news.
        2. Do NOT invent numbers or events.
        3. Only explain stock movements based on tool outputs.
        4. If information is insufficient, say "insufficient data" instead of guessing.

        Output format:

        MARKET DATA
        (show market tool output)

        NEWS SIGNALS
        (show news headlines)

        ANALYSIS
        (explain in depth likely reason for stock movement based on above data)
        """,

    tools=[
        get_stock_data,
        DuckDuckGoTools(
            enable_search=True,
            enable_news=True,
            fixed_max_results=5
        )
    ],
)