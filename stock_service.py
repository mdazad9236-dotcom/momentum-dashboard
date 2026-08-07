import yfinance as yf
from analysis import TechnicalAnalyzer


class StockService:

    def __init__(self):
        pass

    def get_stock_analysis(self, symbol: str):

        # Convert NSE symbols if needed
        if not symbol.endswith(".NS"):
            yahoo_symbol = f"{symbol}.NS"
        else:
            yahoo_symbol = symbol

        stock = yf.Ticker(yahoo_symbol)

        history = stock.history(
            period="1y",
            interval="1d"
        )

        if history.empty:
            return {
                "success": False,
                "message": "No data found"
            }

        analyzer = TechnicalAnalyzer(history)

        result = analyzer.calculate()

        info = {}

        try:
            info = stock.info
        except Exception:
            pass

        return {
            "success": True,
            "symbol": symbol.upper(),
            "company": info.get("longName", symbol.upper()),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "analysis": result
        }
