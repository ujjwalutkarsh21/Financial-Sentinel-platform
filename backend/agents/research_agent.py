from textwrap import dedent
from agno.agent import Agent
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.models.google import Gemini
from agno.models.nvidia import Nvidia
from agno.vectordb.lancedb import LanceDb, SearchType
from dotenv import load_dotenv
load_dotenv()
from instructions.instructions import research_agent

# 1. Create knowledge with a vector DB
from agno.knowledge.embedder.google import GeminiEmbedder

research_kb = Knowledge(
    vector_db=LanceDb(
        uri="tmp/lancedb",
        table_name="financial_docs",
        search_type=SearchType.hybrid,
        embedder=GeminiEmbedder(id="gemini-embedding-001"),
    ),
)

# 2. Insert PDFs from your directory
research_kb.insert(path="knowledge/", reader=PDFReader())

# 3. Create the agent
research_agent = Agent(
    name="Financial Research Analyst",
    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),
    instructions=research_agent,
    knowledge=research_kb,
    search_knowledge=True,
    markdown=True,
)