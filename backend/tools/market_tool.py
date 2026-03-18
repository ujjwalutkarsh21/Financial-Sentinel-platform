"""Market toolkit — stock data fetching only.

ARCHITECTURE CHANGE
───────────────────
`resolve_and_confirm_ticker` is NO LONGER a tool the LLM calls.

The old design had the LLM call resolve_and_confirm_ticker() which returned
a sentinel string, hoping the streaming worker would intercept it.
Problem: by the time the sentinel appears in event.content it has already
been processed by the LLM, which then writes its OWN confirmation prose —
the HITL UI never fires.

New design (clean separation):
  1. analysis_service extracts the ticker from the user message BEFORE
     calling team.run(), using _resolve_ticker() directly.
  2. If the session has no confirmed ticker yet → yield a "hitl" SSE frame
     immediately, no team.run() called at all.
  3. On /confirm → store the confirmed ticker, then call team.run() with
     the ticker already embedded in the enriched message.
  4. The market tools (get_stock_data etc.) receive the ticker directly
     from the LLM — no resolver tool needed.

This means the LLM only calls data tools, never a confirmation tool.
HITL lives entirely in analysis_service, not inside the agent loop.
"""

import yfinance as yf
from datetime import datetime
from agno.tools.toolkit import Toolkit

# ── Per-session confirmed ticker store ───────────────────────────────
_confirmed_tickers: dict[str, str] = {}


def set_confirmed_ticker(session_id: str, ticker: str) -> None:
    _confirmed_tickers[session_id] = ticker.upper()


def get_confirmed_ticker(session_id: str) -> str | None:
    return _confirmed_tickers.get(session_id)


def clear_confirmed_ticker(session_id: str) -> None:
    _confirmed_tickers.pop(session_id, None)


def clear_all_confirmed_tickers() -> None:
    _confirmed_tickers.clear()


# ── Legacy stubs so old imports don't break ──────────────────────────
def pre_approve_ticker(ticker: str) -> None:
    pass

def consume_pre_approved_ticker(ticker: str) -> bool:
    return False


# ── Company-name → ticker mapping ────────────────────────────────────
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
    """Resolve a company name or raw ticker to an uppercase ticker symbol."""
    cleaned = user_input.strip()
    if not cleaned:
        return ""
    lookup = cleaned.lower()
    if lookup in _COMPANY_TICKER_MAP:
        return _COMPANY_TICKER_MAP[lookup]
    return cleaned.upper()


class MarketToolkit(Toolkit):
    """
    Pure data-fetching toolkit. No HITL tool. No confirmation logic.
    The LLM calls these with a ticker it already knows from context.
    """

    def __init__(self):
        super().__init__(
            name="market_toolkit",
            tools=[
                self.get_stock_data,
                self.get_historical_performance,
                self.get_risk_metrics,
                self.get_technical_indicators,
            ],
            requires_confirmation_tools=[],
        )

    def get_stock_data(self, ticker: str) -> dict:
        """Fetch real-time stock price, open, change, volume and market cap."""
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1d")
        info  = stock.info
        if hist.empty:
            return {"error": f"Could not fetch data for ticker {ticker}"}
        current_price  = float(hist["Close"].iloc[-1])
        open_price     = float(hist["Open"].iloc[0])
        price_change   = current_price - open_price
        percent_change = (price_change / open_price) * 100
        return {
            "ticker":         ticker,
            "current_price":  current_price,
            "open_price":     open_price,
            "price_change":   round(price_change, 2),
            "percent_change": round(percent_change, 2),
            "volume":         info.get("volume", "N/A"),
            "market_cap":     info.get("marketCap", "N/A"),
        }

    def get_historical_performance(self, ticker: str) -> dict:
        """Fetch historical performance (%) for 1W, 1M, 3M, YTD, 1Y, 3Y, 5Y."""
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="5y")
        if hist.empty:
            return {"error": f"Could not fetch historical data for {ticker}"}
        current_price = hist["Close"].iloc[-1]

        def pct(days):
            if len(hist) > days:
                return round(
                    ((current_price - hist["Close"].iloc[-days]) / hist["Close"].iloc[-days]) * 100, 2
                )
            return "N/A"

        current_year = datetime.now().year
        ytd_data = hist[hist.index.year == current_year]
        ytd = "N/A"
        if not ytd_data.empty:
            sp  = ytd_data["Close"].iloc[0]
            ytd = round(((current_price - sp) / sp) * 100, 2)

        return {
            "1_week": pct(5), "1_month": pct(21), "3_months": pct(63),
            "YTD": ytd, "1_year": pct(252), "3_years": pct(756), "5_years": pct(1260),
        }

    def get_risk_metrics(self, ticker: str) -> dict:
        """Fetch Beta and average weekly movement over the last year."""
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y", interval="1wk")
        info  = stock.info
        avg_weekly = "N/A"
        if not hist.empty and len(hist) > 1:
            hist["wr"] = hist["Close"].pct_change().abs() * 100
            avg_weekly = round(hist["wr"].mean(), 2)
        return {
            "beta": info.get("beta", "N/A"),
            "avg_weekly_movement_percent": avg_weekly,
        }

    def get_technical_indicators(self, ticker: str) -> dict:
        """Calculate RSI (14), 50-day SMA, and 200-day SMA."""
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="1y")
        if hist.empty or len(hist) < 50:
            return {"error": "Not enough data for technical indicators."}
        close   = hist["Close"]
        sma_50  = round(close.rolling(50).mean().iloc[-1], 2) if len(hist) >= 50  else "N/A"
        sma_200 = round(close.rolling(200).mean().iloc[-1], 2) if len(hist) >= 200 else "N/A"
        delta   = close.diff()
        gain    = delta.where(delta > 0, 0).rolling(14).mean()
        loss    = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs      = gain / loss
        rsi     = round(float(100 - (100 / (1 + rs.iloc[-1]))), 2)
        return {
            "rsi_14":        rsi,
            "sma_50":        sma_50,
            "sma_200":       sma_200,
            "current_price": round(float(close.iloc[-1]), 2),
        }


# Singleton used by market_Agent.py
market_toolkit = MarketToolkit()