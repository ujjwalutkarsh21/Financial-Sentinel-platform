from agents.stock_agent import stock_agent


def main():

    print("Financial Stock Analyst")
    print("-----------------------")

    while True:

        query = input("\nAsk a question: ")

        if query.lower() in ["exit", "quit"]:
            break

        response = stock_agent.run(query)

        print("\nAI Analysis:\n")
        print(response.content)


if __name__ == "__main__":
    main()