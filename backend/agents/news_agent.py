from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()

news_agent = Agent(
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[
        DuckDuckGoTools(
            enable_search=True,
            enable_news=True,
            fixed_max_results=5
        )
    ],

    instructions=dedent("""
    You are a financial news analyst.

    Find the most recent news affecting a stock.

    Summarize the top headlines and explain
    whether they are bullish, bearish, or neutral.

    Always call search_news before answering.
    """),

    markdown=True
)