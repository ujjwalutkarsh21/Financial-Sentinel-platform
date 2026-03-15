from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent
from tools.market_tool import get_stock_data, get_historical_performance, get_risk_metrics, get_technical_indicators
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import market_agent as market_agent_instructions

market_agent = Agent(
    name="Market Data Agent",
    role="Fetch real-time stock prices, volume, market cap, historical performance, risk metrics (beta), and technical indicators using yfinance",
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[get_stock_data, get_historical_performance, get_risk_metrics, get_technical_indicators],

    instructions=market_agent_instructions,

    markdown=True,
)