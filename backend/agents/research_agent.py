from agno.agent import Agent
from agno.models.google import Gemini
from agno.knowledge import PDFKnowledgeBase
from textwrap import dedent
from dotenv import load_dotenv
load_dotenv()

# Load financial document knowledge base
research_kb = PDFKnowledgeBase(
    path="knowledge/"
)

research_agent = Agent(
    name="Financial Research Analyst",

    model=Gemini(id="gemini-2.5-flash"),

    instructions=dedent("""
        You are a financial research analyst.

        Use retrieved financial documents to analyze:

        - revenue trends
        - earnings guidance
        - risks
        - strategic initiatives

        Focus only on information present in the documents.
        Do not invent financial data.
        Provide concise insights useful for stock analysis.
    """),

    knowledge=research_kb,

    search_knowledge=True,

    markdown=True
)