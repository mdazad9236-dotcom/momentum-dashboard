import time

from angel_symbols import get_stock_universe
from angel_service import AngelOneService
from angel_market import AngelMarketData


class AngelScanner:

    def __init__(self):

        self.auth_service = AngelOneService()
        self.market = None

    # =========================================================
    # CONNECT TO ANGEL ONE
    # =========================================================

    def connect(self):

        result = self.auth_service.login()

        if not result.get("success"):

            return {
                "success": False,
                "message": result.get(
                    "message",
                    "Angel One login failed."
                )
            }

        self.market = AngelMarketData(
            self.auth_service.smart_api
        )

        return {
            "success": True,
            "message": "Scanner connected to Angel One."
        }

    # =========================================================
    # SCAN ONE STOCK
    # =========================================================

    def scan_stock(self, stock):

        if self.market is None:

            return {
                "success": False,
                "message": "Scanner is not connected."
            }

        try:

            data = self.market.get_ltp(
                exchange="NSE",
                tradingsymbol=stock["symbol"],
                symboltoken=stock["token"]
            )

            if not data.get("success"):

                return {
                    "success": False,
                    "symbol": stock["symbol"],
                    "name": stock["name"],
                    "message": data.get(
                        "message",
                        "Unable to fetch data."
                    )
                }

            return {
                "success": True,
                "symbol": stock["symbol"],
                "name": stock["name"],
                "token": stock["token"],
                "ltp": data.get("ltp"),
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close")
            }

        except Exception as error:

            return {
                "success": False,
                "symbol": stock["symbol"],
                "name": stock["name"],
                "message": str(error)
            }

    # =========================================================
    # SCAN ALL STOCKS
    # =========================================================

    def scan_market(self):

        connection = self.connect()

        if not connection.get("success"):

            return {
                "success": False,
                "message": connection.get("message"),
                "stocks": []
            }

        universe = get_stock_universe()

        results = []

        for stock in universe:

            result = self.scan_stock(stock)

            if result.get("success"):

                results.append(result)

            # Small delay to avoid hammering the API.
            time.sleep(0.15)

        return {
            "success": True,
            "count": len(results),
            "stocks": results
        }
