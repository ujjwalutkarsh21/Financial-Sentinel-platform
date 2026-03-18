from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

sentiment_agent = Agent(
    name="Financial News Sentiment Analyst",
    role="Analyze financial news headlines and classify overall sentiment as Bullish, Neutral, or Bearish with a score",
    model=AzureOpenAI(id="gpt-5.2-chat"),
    instructions=[
        "You are a financial sentiment analyst.",
        "You receive a list of news headlines about a stock or market topic.",
        "",
        "Your job:",
        "1. Classify each headline as Bullish, Neutral, or Bearish.",
        "2. Compute an overall sentiment score from -1.0 (fully bearish) to +1.0 (fully bullish).",
        "3. Identify the 2-3 main sentiment drivers.",
        "",
        "Return your analysis in this exact plain-text format (no JSON, no code blocks):",
        "",
        "Sentiment: [Bullish / Neutral / Bearish]",
        "Score: [e.g. +0.6]",
        "Breakdown: [X] Bullish, [Y] Neutral, [Z] Bearish",
        "Key drivers: [driver 1], [driver 2], [driver 3]",
        "Summary: [1-2 sentence plain-English summary of the dominant sentiment narrative]",
        "",
        "Do NOT output JSON. Do NOT add any other text.",
    ],
    markdown=True,
)