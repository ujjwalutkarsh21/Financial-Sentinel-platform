import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from agno.tools.toolkit import Toolkit


class MarketToolkit(Toolkit):
    """
    Custom toolkit wrapping all market-data fetching functions.
    All four tools require human confirmation so the user can
    verify the ticker before any real API calls are made.
    """

    def __init__(self):
        # Pass the bound methods via `tools=` so that Agno's internal validation
        # of `requires_confirmation_tools` runs AFTER the tools are registered.
        super().__init__(
            name="market_toolkit",
            tools=[
                self.get_stock_data,
                self.get_historical_performance,
                self.get_risk_metrics,
                self.get_technical_indicators,
            ],
            requires_confirmation_tools=[
                "get_stock_data",
                "get_historical_performance",
                "get_risk_metrics",
                "get_technical_indicators",
            ],
        )

    # ------------------------------------------------------------------
    # Tools
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