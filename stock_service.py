import yfinance as yf
from analysis import TechnicalAnalyzer


class StockService:

    def __init__(self):
        pass

    def get_stock_analysis(self, symbol: str):

        symbol = symbol.upper().strip()

        if not symbol:
            return {
                "success": False,
                "message": "Stock symbol is required."
            }

        # Convert NSE/BSE symbol to Yahoo Finance format
        if symbol.endswith(".NS") or symbol.endswith(".BO"):
            yahoo_symbol = symbol
        else:
            yahoo_symbol = f"{symbol}.NS"

        try:

            # -------------------------------------------------
            # FETCH MARKET DATA
            # -------------------------------------------------

            stock = yf.Ticker(yahoo_symbol)

            history = stock.history(
                period="1y",
                interval="1d",
                auto_adjust=False
            )

            if history is None or history.empty:

                return {
                    "success": False,
                    "message": f"No market data found for {symbol}."
                }

            # -------------------------------------------------
            # TECHNICAL ANALYSIS
            # -------------------------------------------------

            analyzer = TechnicalAnalyzer(history)

            analysis = analyzer.calculate()

            # -------------------------------------------------
            # COMPANY INFORMATION
            # -------------------------------------------------

            try:
                info = stock.info
            except Exception:
                info = {}

            clean_symbol = (
                symbol
                .replace(".NS", "")
                .replace(".BO", "")
            )

            return {

                "success": True,

                "symbol": clean_symbol,

                "company": info.get(
                    "longName",
                    clean_symbol
                ),

                "sector": info.get(
                    "sector",
                    "Unknown"
                ),

                "industry": info.get(
                    "industry",
                    "Unknown"
                ),

                "analysis": analysis
            }

        except Exception as error:

            return {
                "success": False,
                "message": str(error)
            }


# =============================================================
# BACKWARD-COMPATIBLE FUNCTION
# =============================================================

def get_stock_data(symbol: str):

    symbol = symbol.upper().strip()

    if not symbol:
        return None

    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        yahoo_symbol = symbol
    else:
        yahoo_symbol = f"{symbol}.NS"

    try:

        stock = yf.Ticker(yahoo_symbol)

        history = stock.history(
            period="1y",
            interval="1d",
            auto_adjust=False
        )

        if history is None or history.empty:
            return None

        return history

    except Exception:
        return None
