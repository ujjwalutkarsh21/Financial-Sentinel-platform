from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent


query_analyzer = Agent(
    model=Groq(id="openai/gpt-oss-120b"),

    instructions=dedent("""
    You are a query analysis system.

    Your task is to convert a user financial question
    into structured JSON.

    Extract the following fields:

    intent:
        stock_analysis
        general_finance
        unknown

    company:
        company name if present

    ticker:
        stock ticker if identifiable

    query_type:
        price_movement
        news_analysis
        general_question

    timeframe:
        today
        recent
        unknown

    Return ONLY JSON.
    """),

    markdown=False
)

def analyze_query(query: str):

    response = query_analyzer.run(query)

    return response.content