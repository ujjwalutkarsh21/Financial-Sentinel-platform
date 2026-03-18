from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

from tools.market_tool import market_toolkit

market_agent = Agent(
    name="Market Data Agent",
    role="Fetch real-time stock prices, volume, market cap, historical performance, risk metrics, and technical indicators",
    model=AzureOpenAI(id="gpt-5.2-chat"),
    tools=[market_toolkit],
    instructions=[
        "You are a stock market data analyst.",
        "The ticker symbol has already been confirmed — it is provided in the task message.",
        "Use it directly. Do NOT ask for confirmation.",
        "",
        "Call ALL FOUR tools in sequence with the given ticker:",
        "  1. get_stock_data(ticker)",
        "  2. get_historical_performance(ticker)",
        "  3. get_risk_metrics(ticker)",
        "  4. get_technical_indicators(ticker)",
        "",
        "Return the raw data clearly structured.",
        "Classify the 1-day move: minor (<1%), moderate (1–3%), significant (>3%).",
        "Focus only on numbers. No speculation about news or fundamentals.",
    ],
    markdown=True,
)