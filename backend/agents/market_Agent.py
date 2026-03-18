from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import market_agent as market_agent_instructions
from tools.market_tool import market_toolkit

market_agent = Agent(
    name="Market Data Agent",
    role="Fetch real-time stock prices, volume, market cap, historical performance, risk metrics (beta), and technical indicators using yfinance",
    model=AzureOpenAI(id="gpt-5.2-chat"),

    tools=[market_toolkit],

    instructions=market_agent_instructions,

    markdown=True,
)