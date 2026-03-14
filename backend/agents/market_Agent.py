from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent
from tools.market_tool import get_stock_data
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import market_agent

market_agent = Agent(
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[get_stock_data],

    instructions=market_agent,

    markdown=True
)