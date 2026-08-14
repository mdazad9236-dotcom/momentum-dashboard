import json
import os
import requests
from datetime import datetime


INSTRUMENT_URL = (
    "https://margincalculator.angelbroking.com/"
    "OpenAPI_File/files/OpenAPIScripMaster.json"
)

CACHE_FILE = "angel_instruments.json"


class AngelInstrumentManager:

    def __init__(self):
        self.instruments = []

    # ==========================================================
    # DOWNLOAD MASTER
    # ==========================================================

    def download_master(self):

        try:
            response = requests.get(
                INSTRUMENT_URL,
                timeout=30
            )

            response.raise_for_status()

            data = response.json()

            if not isinstance(data, list):
                raise ValueError(
                    "Invalid Angel One instrument data."
                )

            with open(
                CACHE_FILE,
                "w",
                encoding="utf-8"
            ) as file:

                json.dump(
                    data,
                    file
                )

            self.instruments = data

            print(
                f"Angel One instruments downloaded: {len(data)}"
            )

            return {
                "success": True,
                "count": len(data),
                "message": "Instrument master downloaded."
            }

        except Exception as error:

            print(
                "Instrument download error:",
                error
            )

            return {
                "success": False,
                "count": 0,
                "message": str(error)
            }

    # ==========================================================
    # LOAD CACHE
    # ==========================================================

    def load_cache(self):

        if not os.path.exists(CACHE_FILE):
            return self.download_master()

        try:

            with open(
                CACHE_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                self.instruments = json.load(file)

            return {
                "success": True,
                "count": len(self.instruments),
                "message": "Instrument cache loaded."
            }

        except Exception:

            return self.download_master()

    # ==========================================================
    # REFRESH
    # ==========================================================

    def refresh(self):

        return self.download_master()

    # ==========================================================
    # NSE EQUITY STOCKS
    # ==========================================================

    def get_nse_equities(self):

        if not self.instruments:
            self.load_cache()

        stocks = []

        for item in self.instruments:

            if not isinstance(item, dict):
                continue

            if item.get("exch_seg") != "NSE":
                continue

            symbol = str(
                item.get("symbol", "")
            ).strip()

            token = str(
                item.get("token", "")
            ).strip()

            name = str(
                item.get("name", "")
            ).strip()

            instrument_type = str(
                item.get("instrumenttype", "")
            ).strip()

            # We only want normal NSE equity.
            if not symbol.endswith("-EQ"):
                continue

            if not token:
                continue

            stocks.append({
                "symbol": symbol,
                "token": token,
                "name": name,
                "exchange": "NSE",
                "instrumenttype": instrument_type
            })

        return stocks

    # ==========================================================
    # FIND STOCK
    # ==========================================================

    def find_stock(self, symbol):

        if not self.instruments:
            self.load_cache()

        symbol = symbol.upper().strip()

        for item in self.instruments:

            if (
                item.get("exch_seg") == "NSE"
                and item.get("symbol", "").upper()
                == symbol
            ):
                return item

        return None

    # ==========================================================
    # GET TOKEN
    # ==========================================================

    def get_token(self, symbol):

        stock = self.find_stock(symbol)

        if not stock:
            return None

        return str(
            stock.get("token")
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def summary(self):

        stocks = self.get_nse_equities()

        return {
            "success": True,
            "count": len(stocks),
            "updated": datetime.now().isoformat(),
            "stocks": stocks
        }
