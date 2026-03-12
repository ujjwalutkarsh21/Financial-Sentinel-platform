from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent
from tools.market_tool import get_stock_data


market_agent = Agent(
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[get_stock_data],

    instructions=dedent("""
    You are a stock market data analyst.

    Your job is to interpret stock price movements.

    Always call the market data tool first.

    Output format:

    MARKET DATA
    Show the raw data.

    MARKET INTERPRETATION
    Explain whether the movement is large or minor.
    """),

    markdown=True
)