from agents.stock_agent import stock_agent
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

        response = stock_agent.run(structured_prompt)
        # response = stock_agent.run(query)
        print("\n structure query:", structured_query)
        print("\nAI Analysis:\n")
        print(response.content)


if __name__ == "__main__":
    main()