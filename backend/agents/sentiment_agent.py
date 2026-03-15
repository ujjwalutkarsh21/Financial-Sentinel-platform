from agno.agent import Agent
from agno.models.nvidia import Nvidia
from dotenv import load_dotenv
load_dotenv()

sentiment_agent = Agent(
    name="Financial News Sentiment Analyst",

    role="Analyze financial news headlines and classify sentiment as Bullish, Neutral, or Bearish with a score from -1 to +1",

    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions = [
    "Classify each headline as Bullish, Neutral, or Bearish.",
    "Count the number of headlines in each category.",
    "Compute a sentiment score between -1 and +1.",
    "Return structured JSON only.",
    "Do not explain anything outside JSON."
    ],

    markdown=True
)