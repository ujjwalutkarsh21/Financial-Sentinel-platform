from agents.team_orchestrator import financial_sentinel


# =====================================================================
#  Corp8AI Financial Sentinel — Entry Point
#  -------------------------------------------------------------------
#  All orchestration is handled by the Agno Team leader.
#  No manual agent chaining needed.
# =====================================================================

def main():

    print()
    print("=" * 55)
    print("   Corp8AI Financial Sentinel")
    print("   Auditable Multi-Agent Intelligence for Finance")
    print("=" * 55)
    print()
    print("  Specialist Agents:")
    print("    • Market Data Agent    — real-time stock prices")
    print("    • News Agent           — latest financial headlines")
    print("    • Sentiment Analyst    — bullish / bearish scoring")
    print("    • Research Analyst     — deep RAG on SEC filings")
    print("    • Signal Validator     — contradiction detection")
    print()
    print("  Type 'exit' or 'quit' to stop.")
    print("-" * 55)

    while True:

        query = input("\n📊 Ask a question: ")

        if query.strip().lower() in ["exit", "quit"]:
            print("\nGoodbye!\n")
            break

        if not query.strip():
            continue

        print()
        financial_sentinel.print_response(query, stream=True)


if __name__ == "__main__":
    main()