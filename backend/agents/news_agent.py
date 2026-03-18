from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.tools.duckduckgo import DuckDuckGoTools
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import news_agent as news_agent_instructions

news_agent = Agent(
    name="News Agent",
    role="Search for the latest financial news headlines using DuckDuckGo",
    model=AzureOpenAI(id="gpt-5.2-chat"),

    tools=[
        DuckDuckGoTools(
            enable_search=True,
            enable_news=True,
            fixed_max_results=5
        )
    ],

    instructions=news_agent_instructions,

    markdown=True,
)