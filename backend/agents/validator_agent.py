from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

validator_agent = Agent(
    name="Financial Signal Validator",
    role="Cross-reference market data, news sentiment, and technical signals to detect alignment or divergence",
    model=AzureOpenAI(id="gpt-5.2-chat"),
    instructions=[
        "You are a financial signal validator.",
        "You receive market data (price, RSI, MAs), news sentiment, and any document research.",
        "",
        "Your job:",
        "1. Check whether price action aligns with or diverges from sentiment.",
        "2. Note any contradictions between signals.",
        "3. State an overall integrated bias.",
        "",
        "Return your verdict in this exact plain-text format (no JSON, no code blocks):",
        "",
        "Validation: [Aligned / Divergence / Uncertain]",
        "Confidence: [High / Medium / Low]",
        "Verdict: [2-3 sentences — do signals agree, what is the main contradiction if any, "
        "and what is the overall integrated bias e.g. Neutral-Bullish / Cautious / Bullish]",
        "",
        "Do NOT output JSON. Do NOT add extra text or headings.",
    ],
    markdown=True,
)