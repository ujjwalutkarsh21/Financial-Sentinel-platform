#this tool is not currently in function as we have used inbuilt ddgs tool from agno agent for better response

from ddgs import DDGS


def search_news(company: str):

    query = f"{company} stock"

    articles = []

    with DDGS() as ddgs:
        for r in ddgs.news(query, max_results=5):

            articles.append({
                "title": r.get("title", ""),
                "source": r.get("source", ""),
                "date": r.get("date", ""),
                "snippet": r.get("body", ""),
                "link": r.get("url", "")
            })

    # print("articles -------------------------------------") #just checking if the tool is working or not
    # print(articles)

    return articles[:3]