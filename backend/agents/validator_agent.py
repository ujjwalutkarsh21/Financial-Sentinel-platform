from agno.agent import Agent
from agno.models.nvidia import Nvidia
from textwrap import dedent
import json
import re
from dotenv import load_dotenv
load_dotenv()

validator_agent = Agent(

    name="Financial Signal Validator",
    role="Cross-reference all agent findings to detect contradictions between market data, news sentiment, and document research",

    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions=dedent("""
        You are a financial validation system.

        Your job is to verify whether financial signals agree or contradict.

        Inputs you will receive:
        - Market data summary
        - News signals
        - Sentiment analysis
        - Aggregated explanation

        Tasks:
        1. Check if market movement matches sentiment.
        2. Check if news signals support the market move.
        3. Detect contradictions.

        Return strict below JSON only.

        Schema:

        {
         "validation_status": "aligned | divergence | uncertain",
         "reason": "short explanation",
         "confidence": "high | medium | low"
        }
    """),

    markdown=False
)

def validate_analysis(input_data: str):

    response = validator_agent.run(input_data)

    content = response.content.strip()

    content = re.sub(r"```json|```", "", content).strip()

    try:
        validation = json.loads(content)
    except:
        validation = {
            "validation_status": "uncertain",
            "reason": "validator parsing failed",
            "confidence": "low"
        }

    return validation