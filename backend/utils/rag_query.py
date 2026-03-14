from textwrap import dedent
from agno.agent import Agent
from agno.models.nvidia import Nvidia
from dotenv import load_dotenv
load_dotenv()

rag_query_writer = Agent(
    name="Financial RAG Query Rewriter",

    model=Nvidia(id="meta/llama-4-maverick-17b-128e-instruct"),

    instructions=dedent("""
        You are a financial query rewriting system.

        Your task is to convert a user investment question
        into a precise financial research query suitable for
        retrieving information from financial documents such as:

        - earnings reports
        - annual reports (10-K)
        - quarterly reports (10-Q)
        - investor presentations
        - industry reports

        The rewritten query should focus on retrieving information about:

        • revenue trends
        • earnings guidance
        • segment performance
        • AI and data center demand
        • strategic initiatives
        • competitive risks
        • regulatory risks
        • industry outlook

        Rules:
        1. Produce a concise research query optimized for document retrieval.
        2. Use financial terminology commonly found in financial reports.
        3. Do NOT answer the question.
        4. Do NOT include explanations.
        5. Output only the improved research query.

        Example:

        User Question:
        "Should I invest in Nvidia today?"

        Rewritten Query:
        "Analyze Nvidia's recent revenue growth, earnings guidance,
        AI data center demand, and key business risks based on recent
        financial reports and semiconductor industry outlook."
    """),

    markdown=False
)

def rag_query_rewriter(query: str):

    response = rag_query_writer.run(query)

    return response.content