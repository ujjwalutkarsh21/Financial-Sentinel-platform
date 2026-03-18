from agno.agent import Agent
from agno.models.azure import AzureOpenAI
from agno.tools.duckduckgo import DuckDuckGoTools
from dotenv import load_dotenv

load_dotenv()

news_agent = Agent(
    name="News Agent",
    role="Search for the latest financial news headlines using DuckDuckGo",
    model=AzureOpenAI(id="gpt-5.2-chat"),
    tools=[
        DuckDuckGoTools(
            enable_search=True,
            enable_news=True,
            fixed_max_results=5,
        )
    ],
    instructions=[
        "You are a financial news analyst.",
        "When given a stock or company name, search for the 5 most recent relevant headlines.",
        "Return:",
        "  - Each headline with source and date",
        "  - The dominant narrative in 2-3 sentences (earnings / macro / analyst / regulatory / M&A)",
        "Focus on factual headline reporting. Do not editorialize.",
        "",
        "If the query is a greeting or unrelated to stocks, respond briefly without calling any tools.",
    ],
    markdown=True,
)