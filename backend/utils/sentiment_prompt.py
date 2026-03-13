def build_sentiment_prompt(news_output):

    prompt = f"""
    Analyze the sentiment of the following financial news headlines.

    News Headlines:
    {news_output}

    Steps:
    1. Classify each headline as:
       - Bullish
       - Neutral
       - Bearish

    2. Count the number of headlines in each category.

    3. Compute a sentiment score between -1 and +1.

    Return JSON in this format:

    {{
        "bullish_articles": number,
        "neutral_articles": number,
        "bearish_articles": number,
        "sentiment_score": float,
        "overall_sentiment": "Bullish/Neutral/Bearish"
    }}
    """

    return prompt