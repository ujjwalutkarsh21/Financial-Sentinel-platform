from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv
load_dotenv()

sentiment_agent = Agent(
    name="Financial News Sentiment Analyst",

    role="""
    You are a financial sentiment analyst.
    Your task is to analyze financial news headlines related to a stock
    and determine the overall sentiment.
    """,

    model=Gemini(id="gemini-2.5-flash-lite"),

    instructions=[
        "Read the financial news headlines carefully.",
        "Classify each headline as Bullish, Neutral, or Bearish.",
        "Count how many headlines fall into each category.",
        "Compute a sentiment score between -1 and +1.",
        "Return structured JSON only."
    ],

    markdown=True
)