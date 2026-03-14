from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools.duckduckgo import DuckDuckGoTools
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()
from backend.instructions.instructions import news_agent
news_agent = Agent(
    model=Groq(id="openai/gpt-oss-120b"),

    tools=[
        DuckDuckGoTools(
            enable_search=True,
            enable_news=True,
            fixed_max_results=5
        )
    ],

    instructions=news_agent,

    markdown=True
)