import yfinance as yf
from analysis import TechnicalAnalyzer


class StockService:

    def __init__(self):
        pass

    def get_stock_analysis(self, symbol: str):
        symbol = symbol.upper().strip()

        if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
            yahoo_symbol = f"{symbol}.NS"
        else:
            yahoo_symbol = symbol

        try:
            stock = yf.Ticker(yahoo_symbol)
            history = stock.history(period="1y", interval="1d")

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

            clean_sym = symbol.replace(".NS", "").replace(".BO", "")
            return {
                "success": True,
                "symbol": clean_sym,
                "company": info.get("longName", clean_sym),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "analysis": analysis
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e)
            }


def get_stock_data(symbol: str):
    """ Functional wrapper to fetch DataFrame history for app.py """
    symbol = symbol.upper().strip()
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        yahoo_symbol = f"{symbol}.NS"
    else:
        yahoo_symbol = symbol

    try:
        stock = yf.Ticker(yahoo_symbol)
        history = stock.history(period="1y", interval="1d")
        if history.empty:
            return None
        return history
    except Exception:
        return None
