from agno.agent import Agent
from agno.models.nvidia import Nvidia
from textwrap import dedent
from tools.market_tool import get_stock_data
from dotenv import load_dotenv
load_dotenv()

market_agent = Agent(
    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

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