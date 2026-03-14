from agents.aggregator_agent import aggregator_agent
from agents.market_Agent import market_agent
from agents.news_agent import news_agent
from agents.sentiment_agent import sentiment_agent
from agents.validator_agent import validate_analysis
from agents.research_agent import research_agent, research_kb

from utils.sentiment_prompt import build_sentiment_prompt
from utils.query_analyzer import analyze_query
from utils.rag_query import rag_query_rewriter

def main():

    print("Financial Stock Analyst")
    print("-----------------------")

    while True:

        query = input("\nAsk a question: ")

        if query.lower() in ["exit", "quit"]:
            break
        
        structured_query = analyze_query(query)
        rag_query = rag_query_rewriter(query)
        # print(structured_query)
        # break
        structured_prompt = f"""
            User question: {query}

            Structured interpretation:
                {structured_query}

            Use this structured data to answer the question.
            """

        #RUN AGENT ----------------------------------------
        
        market_result = market_agent.run(structured_prompt)
        news_result = news_agent.run(structured_prompt)

        #SENTIMENT AGENT ----------------------------------

        sentiment_prompt = build_sentiment_prompt(news_result.content)
        sentiment_result = sentiment_agent.run(sentiment_prompt)

        combined_input = f"""
        user query : {structured_prompt}
        Market Agent output: {market_result.content}
        News Agent output: {news_result.content}
        Sentiment Analysis: {sentiment_result}
        """
        response = aggregator_agent.run(combined_input)
        
        #validating the output via validator agent
        analysis = response.content
        validation = validate_analysis(analysis)
        
        # print("\n structure query:", structured_query)
        print("\nAI Analysis:\n")
        print(response.content)
        print("\nValidation Report:\n")

        print(validation["validation_status"])

        print("Reason:", validation["reason"])

        print("Confidence:", validation["confidence"])
        
        # --- NEW: Trigger RAG if signals conflict ---
        if validation["validation_status"] == "divergence":

            print("\nDivergence detected. Running deeper research...\n")

            research_result = research_agent.run(f"From financial documents analyze Nvidia fundamentals: revenue trends, earnings guidance, risks based on provided {rag_query}")

            research_text = research_result.content

            print("\nResearch Insights:\n")
            print(research_text)

            # Re-run aggregator with research context
            reanalysis_input = f"""
            Original user query:
            {query}

            Initial analysis:
            {analysis}

            Research insights from financial documents:
            {research_text}

            Provide an updated financial analysis.
            """

            updated_response = aggregator_agent.run(reanalysis_input)

            print("\nUpdated Analysis After Research:\n")
            print(updated_response.content)

if __name__ == "__main__":
    main()