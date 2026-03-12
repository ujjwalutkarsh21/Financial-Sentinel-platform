from agents.aggregator_agent import aggregator_agent
from agents.market_Agent import market_agent
from agents.news_agent import news_agent
from utils.query_analyzer import analyze_query

def main():

    print("Financial Stock Analyst")
    print("-----------------------")

    while True:

        query = input("\nAsk a question: ")

        if query.lower() in ["exit", "quit"]:
            break
        
        structured_query = analyze_query(query)
        structured_prompt = f"""
            User question: {query}

            Structured interpretation:
                {structured_query}

            Use this structured data to answer the question.
            """

        # response = stock_agent.run(structured_prompt)
        # response = stock_agent.run(query)
        market_result = market_agent.run(structured_prompt)
        news_result = news_agent.run(structured_prompt)

        combined_input = f"""
        user query : {structured_prompt}
        Market Agent output: {market_result.content}
        News Agent output: {news_result.content}
        """
        response = aggregator_agent.run(combined_input)

        # print("\n structure query:", structured_query)
        print("\nAI Analysis:\n")
        print(response.content)


if __name__ == "__main__":
    main()