from agno.agent import Agent
from agno.models.groq import Groq
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import market_agent as market_agent_instructions
from tools.market_tool import market_toolkit

market_agent = Agent(
    name="Market Data Agent",
    role="Fetch real-time stock prices, volume, market cap, historical performance, risk metrics (beta), and technical indicators using yfinance",
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[market_toolkit],

    instructions=market_agent_instructions,

    markdown=True,
)