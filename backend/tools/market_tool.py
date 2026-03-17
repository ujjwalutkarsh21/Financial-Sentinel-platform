import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from agno.tools.toolkit import Toolkit


# ── Company-name → ticker mapping ──────────────────────────────────
# Extend this dict freely; it only needs to cover popular names.
_COMPANY_TICKER_MAP: dict[str, str] = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL",
    "alphabet": "GOOGL", "amazon": "AMZN", "meta": "META",
    "facebook": "META", "tesla": "TSLA", "nvidia": "NVDA",
    "netflix": "NFLX", "amd": "AMD", "intel": "INTC",
    "ibm": "IBM", "salesforce": "CRM", "oracle": "ORCL",
    "adobe": "ADBE", "paypal": "PYPL", "uber": "UBER",
    "spotify": "SPOT", "snap": "SNAP", "twitter": "X",
    "coinbase": "COIN", "palantir": "PLTR", "snowflake": "SNOW",
    "shopify": "SHOP", "zoom": "ZM", "airbnb": "ABNB",
    "disney": "DIS", "boeing": "BA", "jpmorgan": "JPM",
    "jp morgan": "JPM", "goldman sachs": "GS", "goldman": "GS",
    "bank of america": "BAC", "wells fargo": "WFC",
    "berkshire": "BRK-B", "berkshire hathaway": "BRK-B",
    "coca-cola": "KO", "coca cola": "KO", "pepsi": "PEP",
    "pepsico": "PEP", "walmart": "WMT", "costco": "COST",
    "nike": "NKE", "visa": "V", "mastercard": "MA",
    "johnson & johnson": "JNJ", "j&j": "JNJ", "pfizer": "PFE",
    "moderna": "MRNA", "eli lilly": "LLY", "lilly": "LLY",
    "exxon": "XOM", "exxonmobil": "XOM", "chevron": "CVX",
    "broadcom": "AVGO", "qualcomm": "QCOM", "micron": "MU",
    "arm": "ARM", "arm holdings": "ARM",
    "reliance": "RELIANCE.NS", "tata": "TCS.NS", "infosys": "INFY",
    "tcs": "TCS.NS", "wipro": "WIPRO.NS", "hcl": "HCLTECH.NS",
}


def _resolve_ticker(user_input: str) -> str:
    """
    Resolve raw user input into a normalised ticker symbol.

    Resolution order:
      1. If it matches a known company name → use the mapped ticker.
      2. Otherwise treat the input itself as a ticker symbol.
    Always returns UPPERCASE.
    """
    cleaned = user_input.strip()
    if not cleaned:
        return ""

    # Try company-name lookup (case-insensitive)
    lookup = cleaned.lower()
    if lookup in _COMPANY_TICKER_MAP:
        return _COMPANY_TICKER_MAP[lookup]

    # Fall through: assume the user typed a ticker directly
    return cleaned.upper()


class MarketToolkit(Toolkit):
    """
    Custom toolkit wrapping all market-data fetching functions.

    HITL strategy:
      • ONE centralized confirmation via `resolve_and_confirm_ticker`.
      • The agent must call this FIRST; the HITL handler shows the
        resolved ticker to the user for confirmation.
      • Once confirmed, the ticker flows into the 4 data tools
        WITHOUT any further confirmation prompts.
    """

    def __init__(self):
        super().__init__(
            name="market_toolkit",
            tools=[
                self.resolve_and_confirm_ticker,
                self.get_stock_data,
                self.get_historical_performance,
                self.get_risk_metrics,
                self.get_technical_indicators,
            ],
            # ── Only the resolver needs human confirmation ──
            requires_confirmation_tools=[
                "resolve_and_confirm_ticker",
            ],
        )

    # ------------------------------------------------------------------
    # Centralized ticker resolution + HITL confirmation
    # ------------------------------------------------------------------

    def resolve_and_confirm_ticker(self, user_input: str) -> str:
        """
        Resolve a company name or ticker symbol and confirm it with the user.

        This function MUST be called before any market-data tool.
        It resolves the input into a valid ticker (e.g. "Tesla" → "TSLA")
        and pauses execution for human-in-the-loop confirmation.

        After confirmation, return the resolved ticker as plain text so
        the agent can pass it to get_stock_data, get_historical_performance,
        get_risk_metrics, and get_technical_indicators.
        """
        resolved = _resolve_ticker(user_input)
        if not resolved:
            return "ERROR: Empty input. Please provide a company name or ticker symbol."

        return f"CONFIRMED_TICKER:{resolved}"

    # ------------------------------------------------------------------
    # Data tools (NO confirmation required — ticker is pre-confirmed)
    # ------------------------------------------------------------------

    def get_stock_data(self, ticker: str) -> dict:
        """Fetch real-time stock price, open price, change, volume and market cap for a given ticker."""
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        info = stock.info

        if hist.empty:
            return {"error": f"Could not fetch data for ticker {ticker}"}

        current_price = float(hist["Close"].iloc[-1])
        open_price = float(hist["Open"].iloc[0])
        price_change = current_price - open_price
        percent_change = (price_change / open_price) * 100

        return {
            "ticker": ticker,
            "current_price": current_price,
            "open_price": open_price,
            "price_change": round(price_change, 2),
            "percent_change": round(percent_change, 2),
            "volume": info.get("volume", "N/A"),
            "market_cap": info.get("marketCap", "N/A"),
        }

    def get_historical_performance(self, ticker: str) -> dict:
        """Fetches historical performance (%) for 1W, 1M, 3M, YTD, 1Y, 3Y, 5Y."""
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5y")

        if hist.empty:
            return {"error": f"Could not fetch historical data for {ticker}"}

        current_price = hist["Close"].iloc[-1]

        def calculate_return(days_back):
            if len(hist) > days_back:
                past_price = hist["Close"].iloc[-days_back]
                return round(((current_price - past_price) / past_price) * 100, 2)
            return "N/A"

        current_year = datetime.now().year
        ytd_data = hist[hist.index.year == current_year]
        ytd_return = "N/A"
        if not ytd_data.empty:
            start_of_year_price = ytd_data["Close"].iloc[0]
            ytd_return = round(
                ((current_price - start_of_year_price) / start_of_year_price) * 100, 2
            )

        return {
            "1_week": calculate_return(5),
            "1_month": calculate_return(21),
            "3_months": calculate_return(63),
            "YTD": ytd_return,
            "1_year": calculate_return(252),
            "3_years": calculate_return(756),
            "5_years": calculate_return(1260),
        }

    def get_risk_metrics(self, ticker: str) -> dict:
        """Fetches Beta and calculates average weekly movement over the last year."""
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y", interval="1wk")
        avg_weekly_movement = "N/A"

        if not hist.empty and len(hist) > 1:
            hist["Weekly_Return"] = hist["Close"].pct_change().abs() * 100
            avg_weekly_movement = round(hist["Weekly_Return"].mean(), 2)

        return {
            "beta": info.get("beta", "N/A"),
            "avg_weekly_movement_percent": avg_weekly_movement,
        }

    def get_technical_indicators(self, ticker: str) -> dict:
        """Calculates RSI (14), 50-day SMA, and 200-day SMA for a given ticker."""
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty or len(hist) < 200:
            return {
                "error": "Not enough data to calculate all technical indicators (need at least 200 days)."
            }

        close_prices = hist["Close"]
        sma_50 = round(close_prices.rolling(window=50).mean().iloc[-1], 2)
        sma_200 = round(close_prices.rolling(window=200).mean().iloc[-1], 2)

        delta = close_prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        current_rsi = round(rsi.iloc[-1], 2)

        return {
            "rsi_14": current_rsi,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "current_price": round(close_prices.iloc[-1], 2),
        }


# Singleton instance used by the Market Agent
market_toolkit = MarketToolkit()