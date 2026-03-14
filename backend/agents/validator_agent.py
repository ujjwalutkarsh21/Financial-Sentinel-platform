from agno.agent import Agent
from agno.models.nvidia import Nvidia
from textwrap import dedent
import json
import re
from dotenv import load_dotenv
load_dotenv()
from backend.instructions.instructions import vaalidator_agent

validator_agent = Agent(

    name="Financial Signal Validator",

    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions=vaalidator_agent,

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