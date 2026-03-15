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
from pydantic import BaseModel
from typing import List

class Insight(BaseModel):
    insight: str
    evidence: str
    source: str

class AnalysisOutput(BaseModel):
    insights: List[Insight]
    not_found: List[str] = []


# 1. Create knowledge with a vector DB
from agno.knowledge.embedder.google import GeminiEmbedder

research_kb = Knowledge(
    vector_db=LanceDb(
        uri="tmp/lancedb",
        table_name="financial_docs",
        search_type=SearchType.vector,
        embedder=GeminiEmbedder(id="gemini-embedding-001"),
    ),
)

# 2. Insert PDFs from your directory
research_kb.insert(path="knowledge/", reader=PDFReader()) #no need to run it again after creating indexing once

# 3. Create the agent
# research_agent = Agent(
#     name="Financial Research Analyst",
#     model=Nvidia(id="microsoft/phi-3-medium-128k-instruct"),
#     instructions=research_agent,
#     knowledge=research_kb,
#     search_knowledge=True,
#     markdown=True,
# )

research_agent = Agent(
    name="Financial Research Analyst",
    role="Deep research on financial documents (SEC filings, earnings reports) using RAG with vector search",
    model=Nvidia(id="microsoft/phi-3-medium-128k-instruct"),
    description="You are a financial research analyst that ONLY uses provided document context.",
    instructions=[
        "Use ONLY information from the DOCUMENT CONTEXT.",
        "Do NOT use prior knowledge or invent facts.",
        "If information is not in documents, say 'Not found in the provided documents.'",
        "Cite evidence with direct quotes for every insight.",
    ],
    use_instruction_tags=True,
    expected_output="Concise bullet points with insights and direct citations from documents.",
    additional_context="CRITICAL: Never fabricate data. Every claim must reference a specific document passage.",
    knowledge=research_kb,
    search_knowledge=True,
    add_knowledge_to_context=True,  # KEY: injects references into user message
    # references_format="json",
    # output_schema=AnalysisOutput,  # Forces structured output
    # structured_outputs=True,
    # reasoning=True,
    # reasoning_min_steps=2,
    markdown=True,
    # debug_mode=True,  # Enable to inspect the compiled system message
)