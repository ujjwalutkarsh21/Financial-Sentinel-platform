from agno.agent import Agent
from agno.models.nvidia import Nvidia
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()

aggregator_agent = Agent(
    # model=Groq(id="openai/gpt-oss-120b"),
    # model=Gemini(id="gemini-2.5-flash"),
    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions=dedent("""
    You are a financial analysis aggregator.

    You receive outputs from multiple specialist agents:
    - Market Agent
    - News Agent

    Your task is to combine their findings into one
    clear financial report.

    Structure the final output like this:

    MARKET DATA
    Show the stock data.

    NEWS SIGNALS
    Summarize the relevant headlines.

    FINAL ANALYSIS
    Explain the most likely reason for the stock movement.
    If there is no clear catalyst, say the movement
    may be normal market fluctuation.
    """),

    markdown=True
)