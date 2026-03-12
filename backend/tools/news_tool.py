from ddgs import DDGS


def search_news(company: str):

    query = f"{company} stock news"

    results = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):
            results.append(r["title"])

    return results