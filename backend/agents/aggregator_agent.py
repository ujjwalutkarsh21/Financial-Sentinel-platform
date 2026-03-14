from agno.agent import Agent
from agno.models.nvidia import Nvidia
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import aggregator_agent

aggregator_agent = Agent(
    # model=Groq(id="openai/gpt-oss-120b"),
    # model=Gemini(id="gemini-2.5-flash"),
    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions=aggregator_agent,

    markdown=True
)