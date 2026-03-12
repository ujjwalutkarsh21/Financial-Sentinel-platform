from ddgs import DDGS


def search_news(company: str):

    query = f"{company} stock news"

    articles = []

    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=5):

            articles.append({
                "title": r["title"],
                "source": r.get("source", "Unknown"),
                "link": r.get("href", "")
            })

    return articles