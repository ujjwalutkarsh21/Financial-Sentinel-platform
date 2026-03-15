"""Quick debug test to check if Groq can handle Team tool calls."""
from agno.team import Team
from agno.team.mode import TeamMode
from agno.agent import Agent
from agno.models.groq import Groq
from dotenv import load_dotenv
load_dotenv()

# Minimal test: 1 agent, 1 team, debug_mode on
test_agent = Agent(
    name="Echo Agent",
    role="Simply echo back whatever task you receive",
    model=Groq(id="openai/gpt-oss-120b"),
    instructions=["Just echo back the task you receive."],
    markdown=True,
)

test_team = Team(
    name="Test Team",
    mode=TeamMode.coordinate,
    model=Groq(id="openai/gpt-oss-120b"),
    members=[test_agent],
    instructions="Delegate any question to the Echo Agent.",
    markdown=True,
    debug_mode=True,
    show_members_responses=True,
)

test_team.print_response("Say hello", stream=True)
