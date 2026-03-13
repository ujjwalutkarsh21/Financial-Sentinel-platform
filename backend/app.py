from agents.aggregator_agent import aggregator_agent
from agents.market_Agent import market_agent
from agents.news_agent import news_agent
from agents.sentiment_agent import sentiment_agent

from utils.sentiment_prompt import build_sentiment_prompt
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

        # print("\n structure query:", structured_query)
        print("\nAI Analysis:\n")
        print(response.content)


if __name__ == "__main__":
    main()