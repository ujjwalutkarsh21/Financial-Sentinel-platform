import requests
import os
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")


def resolve_ticker(company_name: str):

    url = "https://finnhub.io/api/v1/search"

    params = {
        "q": company_name,
        "token": FINNHUB_API_KEY
    }

    try:
        r = requests.get(url, params=params)
        data = r.json()

    except Exception as e:
        return {"error": f"API request failed: {str(e)}"}

    # Check API error
    if "error" in data:
        return {"error": data["error"]}

    # Ensure result exists
    if "result" not in data or not data["result"]:
        return {"error": "Ticker not found"}

    best_match = data["result"][0]

    return {
        "company": best_match.get("description"),
        "ticker": best_match.get("symbol"),
        "type": best_match.get("type")
    }