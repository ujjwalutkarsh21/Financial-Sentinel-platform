import os
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.reader.pdf_reader import PDFReader
from agno.vectordb.lancedb import LanceDb, SearchType
from agno.knowledge.embedder.google import GeminiEmbedder
from dotenv import load_dotenv

load_dotenv()

print("Setting up Knowledge Base...")
research_kb = Knowledge(
    vector_db=LanceDb(
        uri="tmp/lancedb",
        table_name="financial_docs",
        search_type=SearchType.vector,
        embedder=GeminiEmbedder(id="gemini-embedding-001"),
    ),
)
print("Loading a small PDF into LanceDB...")

try:
    # Agno knowledge insert with a single path
    # We only process the small file to avoid Gemini rate limit (40 requests per minute)
    small_pdf_path = "knowledge/nvidia-first-q4-2026.pdf"
    
    if os.path.exists(small_pdf_path):
        print(f"Reading and inserting {small_pdf_path} (86 KB)...")
        research_kb.insert(path=small_pdf_path, reader=PDFReader())
        print("Success! Knowledge base populated with the small document.")
    else:
        print("Could not find the small PDF file.")

except Exception as e:
    print(f"Failed to populate knowledge base: {e}")
