from textwrap import dedent
from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.google import Gemini
from agno.vectordb.lancedb import LanceDb, SearchType
from dotenv import load_dotenv
load_dotenv()

# 1. Create knowledge with a vector DB
research_kb = Knowledge(
    vector_db=LanceDb(
        uri="tmp/lancedb",
        table_name="financial_docs",
        search_type=SearchType.hybrid,
    ),
)

# 2. Insert PDFs from your directory
research_kb.insert(path="knowledge/", reader=PDFReader())

# 3. Create the agent
research_agent = Agent(
    name="Financial Research Analyst",
    model=Gemini(id="gemini-2.5-flash"),
    instructions=dedent("""\
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
    markdown=True,
)