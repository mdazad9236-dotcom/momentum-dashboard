import yfinance as yf
from analysis import TechnicalAnalyzer


class StockService:

    def __init__(self):
        pass

    def get_stock_analysis(self, symbol: str):

        symbol = symbol.upper()

        # Convert NSE symbol
        if not symbol.endswith(".NS"):
            yahoo_symbol = f"{symbol}.NS"
        else:
            yahoo_symbol = symbol

        try:
            stock = yf.Ticker(yahoo_symbol)

            history = stock.history(
                period="1y",
                interval="1d"
            )

            if history.empty:
                return {
                    "success": False,
                    "message": "No historical data found."
                }

            analyzer = TechnicalAnalyzer(history)
            analysis = analyzer.calculate()

            try:
                info = stock.info
            except Exception:
                info = {}

            return {
                "success": True,
                "symbol": symbol.replace(".NS", ""),
                "company": info.get("longName", symbol.replace(".NS", "")),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "analysis": analysis
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }
